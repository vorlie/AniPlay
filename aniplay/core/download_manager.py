# AniPlay - Personal media server and player for anime libraries.
# Copyright (C) 2026  Charlie
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import os
import subprocess
import re
from PyQt6.QtCore import QObject, pyqtSignal
import json
import time
from ..utils.logger import get_logger
from ..config import DOWNLOADS_PATH

logger = get_logger(__name__)

class DownloadTask(QObject):
    progress_updated = pyqtSignal(str, float, str, str, str) # filename, percentage, speed, eta, elapsed
    finished = pyqtSignal(str, bool, str, dict) # filename, success, message, metadata
    
    def __init__(self, url, filename, referrer=None, metadata=None):
        super().__init__()
        self.url = url
        self.filename = filename
        self.referrer = referrer
        self.metadata = metadata or {}
        self.process = None
        self._is_cancelled = False

    async def run(self):
        show_id = self.metadata.get('show_id')
        show_name = self.metadata.get('show_name', 'Unknown')
        base_dir = DOWNLOADS_PATH
        
        if show_id:
            # Hash-only folder names (no series name) for both Nyaa and AllAnime
            if show_id.startswith("nyaa-"):
                # show_id is already the prefixed hash
                base_dir = os.path.join(DOWNLOADS_PATH, show_id)
            elif not show_id.startswith("nyaa-"):
                # For AllAnime, get prefixed hash
                from .online_library_manager import OnlineLibraryManager
                ol_manager = OnlineLibraryManager(DOWNLOADS_PATH, None)
                folder_name = ol_manager.get_allanime_folder_name(show_id)
                base_dir = os.path.join(DOWNLOADS_PATH, folder_name)
            else:
                # Fallback
                safe_id = re.sub(r'[/\\:*?"<>|]', '_', show_id)
                base_dir = os.path.join(DOWNLOADS_PATH, safe_id)
            
            os.makedirs(base_dir, exist_ok=True)
            
        output_path = os.path.join(base_dir, self.filename)
        
        # Check if it's a magnet link
        if self.url.startswith("magnet:"):
            # Use aria2c for torrents/magnets. 
            # --summary-interval=1 for frequent progress updates
            # --bt-tracker-timeout for faster multi-tracker switching
            cmd = ["aria2c", "--seed-time=0", "--allow-overwrite=true", 
                   "--summary-interval=1", "--console-log-level=info",
                   "--human-readable=false", "--enable-color=false",
                   "--bt-tracker-connect-timeout=5", "--bt-tracker-timeout=5",
                   "--dir", base_dir, self.url]
            # Removed -o as it can cause issues with magnets if they contain different file names
            logger.info(f"Starting torrent download via aria2c: {' '.join(cmd)}")
            is_torrent = True
        else:
            # Use ffmpeg for regular URLs (m3u8, direct mp4).
            cmd = ["ffmpeg", "-y"]
            if self.referrer:
                cmd.extend(["-headers", f"Referer: {self.referrer}\r\n"])
            cmd.extend(["-i", self.url, "-stats", "-c", "copy", "-bsf:a", "aac_adtstoasc", output_path])
            logger.info(f"Starting stream download via ffmpeg: {' '.join(cmd)}")
            is_torrent = False

        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            import time
            start_wall_time = time.time()
            duration = 0
            has_started = False
            # Use read(1024) and split by \r or \n to catch all progress updates
            buffer = ""
            while True:
                if is_torrent:
                    # aria2c output parsing
                    chunk = await self.process.stdout.read(1024)
                    if not chunk: break
                    buffer += chunk.decode(errors='replace')
                    lines = re.split(r'[\r\n]+', buffer)
                    if buffer and buffer[-1] not in ['\r', '\n']: buffer = lines.pop()
                    else: buffer = ""
                    
                    for line_str in lines:
                        line_str = line_str.strip()
                        if not line_str: continue
                        
                        # logger.debug(f"aria2: {line_str}") # Hidden to avoid cluttering, but useful for deep debugging
                        
                        # 1. Look for progress: (26%)
                        prog_match = re.search(r'\((\d+)%\)', line_str)
                        # 2. Look for speed: DL:12345 (bytes/s because human-readable=false)
                        speed_match = re.search(r'DL:([\d.]+)', line_str)
                        # 3. Look for ETA: ETA:30s
                        eta_match = re.search(r'ETA:([\d.\w]+)', line_str)
                        
                        if prog_match:
                            try:
                                progress = float(prog_match.group(1))
                                raw_speed = float(speed_match.group(1)) if speed_match else 0
                                
                                # Format speed
                                if raw_speed > 1024 * 1024:
                                    speed_str = f"{raw_speed/(1024*1024):.1f}MiB/s"
                                elif raw_speed > 1024:
                                    speed_str = f"{raw_speed/1024:.1f}KiB/s"
                                else:
                                    speed_str = f"{raw_speed}B/s"
                                    
                                eta = eta_match.group(1) if eta_match else "..."
                                self.progress_updated.emit(self.filename, progress, speed_str, eta, "0:00")
                                has_started = True 
                            except Exception as e:
                                logger.error(f"Error parsing aria2 line: {e} | Line: {line_str}")
                        elif not has_started and any(word in line_str for word in ["Metadata", "DHT", "Peers", "Connecting"]):
                            # Only show "Searching..." if we haven't started actual downloading yet
                            self.progress_updated.emit(self.filename, 0.0, "Searching...", "Wait", "0:00")
                else:
                    # ffmpeg output parsing
                    chunk = await self.process.stderr.read(1024)
                    if not chunk: break
                    buffer += chunk.decode(errors='replace')
                    lines = re.split(r'[\r\n]+', buffer)
                    if buffer and buffer[-1] not in ['\r', '\n']: buffer = lines.pop()
                    else: buffer = ""
                    
                    for line_str in lines:
                        line_str = line_str.strip()
                        if not line_str: continue
                        
                        if not duration:
                            dur_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", line_str)
                            if dur_match:
                                h, m, s = map(float, dur_match.groups())
                                duration = h * 3600 + m * 60 + s
                                logger.info(f"Detected download duration: {duration}s")
                        
                        time_match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line_str)
                        speed_match = re.search(r"speed=\s*([\d.]+[xX]?)", line_str)
                        
                        if time_match:
                            speed_str = speed_match.group(1) if speed_match else "0.0x"
                            try:
                                speed_val = float(re.sub(r'[xX]', '', speed_str))
                            except:
                                speed_val = 0.0
                                
                            h, m, s = map(float, time_match.groups())
                            current_time = h * 3600 + m * 60 + s
                            elapsed_seconds = int(time.time() - start_wall_time)
                            m_el, s_el = divmod(elapsed_seconds, 60)
                            h_el, m_el = divmod(m_el, 60)
                            elapsed_str = f"{h_el}:{m_el:02d}:{s_el:02d}" if h_el > 0 else f"{m_el}:{s_el:02d}"

                            if duration > 0:
                                progress = (current_time / duration) * 100
                                if speed_val > 0:
                                    remaining_seconds = (duration - current_time) / speed_val
                                    m_rem, s_rem = divmod(int(remaining_seconds), 60)
                                    h_rem, m_rem = divmod(m_rem, 60)
                                    eta_str = f"{h_rem}:{m_rem:02d}:{s_rem:02d}" if h_rem > 0 else f"{m_rem}:{s_rem:02d}"
                                else:
                                    eta_str = "Inf"
                                self.progress_updated.emit(self.filename, min(progress, 100.0), speed_str, eta_str, elapsed_str)
                            else:
                                self.progress_updated.emit(self.filename, 0.0, f"{speed_str} @ {int(current_time)}s", "...", elapsed_str)

            await self.process.wait()
            
            if self._is_cancelled:
                if os.path.exists(output_path):
                    os.remove(output_path)
                self.finished.emit(self.filename, False, "Cancelled", self.metadata)
            elif self.process.returncode == 0:
                logger.info(f"Download finished: {self.filename}")
                self.finished.emit(self.filename, True, "Success", self.metadata)
            else:
                logger.error(f"Download failed with code {self.process.returncode}")
                self.finished.emit(self.filename, False, f"Process exited with code {self.process.returncode}", self.metadata)
                
        except Exception as e:
            logger.error(f"Download error: {e}")
            self.finished.emit(self.filename, False, str(e), self.metadata)

    def cancel(self):
        self._is_cancelled = True
        if self.process:
            try:
                self.process.terminate()
            except Exception as e:
                logger.error(f"Error occurred while terminating process for {self.filename}: {e}")
                pass

class DownloadManager(QObject):
    task_progress = pyqtSignal(str, float, str, str, str)
    task_finished = pyqtSignal(str, bool, str, dict)
    queue_updated = pyqtSignal(int) # Number of pending tasks
    
    def __init__(self, db_manager=None):
        super().__init__()
        self.db = db_manager
        self.active_tasks = {} # filename -> DownloadTask
        self.pending_tasks = [] # list of (url, filename, referrer, metadata)
        self.history = [] # list of {filename, success, message, metadata, timestamp}
        self.task_states = {} # filename -> {status, progress, speed, eta, elapsed, metadata}
        self.max_concurrent = 2 # Increased to 2 for better UX
        
        if self.db:
            asyncio.create_task(self._load_from_db())

    def start_download(self, url, filename, referrer=None, metadata=None):
        """Adds a download to the queue."""
        # Ensure filename is safe and has a valid extension (default to .mp4)
        filename = re.sub(r'[/\\:*?"<>|]', '_', filename)
        if not any(filename.lower().endswith(ext) for ext in ['.mp4', '.mkv', '.avi', '.ts', '.mov']):
            filename += ".mp4"

        if filename in self.active_tasks or any(t[1] == filename for t in self.pending_tasks):
            logger.warning(f"Download already in progress or queued for {filename}")
            return False
            
        self.pending_tasks.append((url, filename, referrer, metadata))
        self.task_states[filename] = {
            "status": "Queued",
            "progress": 0.0,
            "speed": "0.0x",
            "eta": "Waiting...",
            "elapsed": "0:00",
            "metadata": metadata or {}
        }
        self.queue_updated.emit(len(self.pending_tasks))
        
        if self.db:
            from ..database.models import DownloadTaskState
            asyncio.create_task(self.db.update_download_task(DownloadTaskState(
                filename=filename, url=url, status="Queued", referrer=referrer,
                metadata_json=json.dumps(metadata or {})
            )))
            
        self._process_queue()
        return True

    def process_queue(self):
        """Public method to manually trigger queue processing."""
        logger.info("Manually triggering queue processing...")
        self._process_queue()

    def _process_queue(self):
        """Starts next tasks if below concurrency limit."""
        while len(self.active_tasks) < self.max_concurrent and self.pending_tasks:
            url, filename, referrer, metadata = self.pending_tasks.pop(0)
            self.queue_updated.emit(len(self.pending_tasks))
            
            task = DownloadTask(url, filename, referrer, metadata)
            task.progress_updated.connect(self._on_task_progress)
            task.finished.connect(self._on_task_finished)
            
            self.active_tasks[filename] = task
            self.task_states[filename]["status"] = "Downloading"
            asyncio.create_task(task.run())

    def _on_task_progress(self, filename, progress, speed, eta, elapsed):
        if filename in self.task_states:
            self.task_states[filename].update({
                "progress": progress,
                "speed": speed,
                "eta": eta,
                "elapsed": elapsed
            })
        self.task_progress.emit(filename, progress, speed, eta, elapsed)

    def _on_task_finished(self, filename, success, message, metadata):
        if filename in self.active_tasks:
            del self.active_tasks[filename]
        
        self.history.insert(0, {
            "filename": filename,
            "success": success,
            "message": message,
            "metadata": metadata,
            "timestamp": time.time()
        })
        
        if filename in self.task_states:
            self.task_states[filename]["status"] = "Finished" if success else "Failed"
            if not success:
                self.task_states[filename]["message"] = message
        
        # Keep history reasonable
        if len(self.history) > 50:
            self.history.pop()

        self.task_finished.emit(filename, success, message, metadata)
        
        if self.db:
            from ..database.models import DownloadTaskState
            state = self.task_states.get(filename, {})
            asyncio.create_task(self.db.update_download_task(DownloadTaskState(
                filename=filename, url="", status="Finished" if success else "Failed",
                progress=state.get("progress", 100.0 if success else 0.0),
                speed=state.get("speed", ""), eta=state.get("eta", ""), elapsed=state.get("elapsed", ""),
                metadata_json=json.dumps(metadata or {})
            )))

        # Start next in queue
        self._process_queue()

    def is_downloading(self, filename):
        return filename in self.active_tasks or any(t[1] == filename for t in self.pending_tasks)

    def force_start_task(self, filename):
        """Tries to move a specific task to the front of the queue and start it."""
        if filename in self.active_tasks:
            return True
            
        # Find in pending
        for i, t in enumerate(self.pending_tasks):
            if t[1] == filename:
                task_data = self.pending_tasks.pop(i)
                self.pending_tasks.insert(0, task_data)
                self._process_queue()
                return True
        return False

    def cancel_download(self, filename):

        # Check pending
        for i, t in enumerate(self.pending_tasks):
            if t[1] == filename:
                self.pending_tasks.pop(i)
                self.queue_updated.emit(len(self.pending_tasks))
                return True

        # Check active
        if filename in self.active_tasks:
            self.active_tasks[filename].cancel()
            if self.db:
                asyncio.create_task(self.db.remove_download_task(filename))
            return True
        return False

    async def _load_from_db(self):
        """Reloads tasks from database on startup."""
        if not self.db: 
            return
        tasks = await self.db.get_all_download_tasks()
        for t in tasks:
            meta = {}
            try: 
                meta = json.loads(t.metadata_json)
            except Exception as e: 
                logger.error(f"Error parsing metadata for {t.filename}: {e}")
                pass
            
            self.task_states[t.filename] = {
                "status": t.status,
                "progress": t.progress,
                "speed": t.speed,
                "eta": t.eta,
                "elapsed": t.elapsed,
                "metadata": meta
            }
            if t.status == "Queued":
                self.pending_tasks.append((t.url, t.filename, t.referrer, meta))
            elif t.status in ["Finished", "Failed", "Cancelled"]:
                self.history.append({
                    "filename": t.filename,
                    "success": t.status == "Finished",
                    "message": t.status if t.status != "Finished" else "Success",
                    "metadata": meta,
                    "timestamp": t.last_updated.timestamp()
                })
        
        if self.pending_tasks:
            self.queue_updated.emit(len(self.pending_tasks))
            self._process_queue()

    def get_local_path(self, filename, show_id=None, ep_no=None):
        # 1. Check in subfolder (New organized way)
        if show_id:
            # Flexible resolution for Nyaa: Scan for folder ending with [show_id] or exact match
            base_dir = None
            if show_id.startswith("nyaa-"):
                # 1. Try exact match (new way)
                path = os.path.join(DOWNLOADS_PATH, show_id)
                if os.path.isdir(path):
                    base_dir = path
                else:
                    # 2. Try suffix match (migration/previous version)
                    match_suffix = f"[{show_id}]"
                    if os.path.exists(DOWNLOADS_PATH):
                        for d in os.listdir(DOWNLOADS_PATH):
                            if d.endswith(match_suffix):
                                base_dir = os.path.join(DOWNLOADS_PATH, d)
                                break
            
            # If not found via suffix or not a Nyaa ID, use exact match/pre-sanitized ID
            if not base_dir:
                if show_id and not show_id.startswith("nyaa-"):
                    # For AllAnime, try:
                    # 1. allanime-hash (new way)
                    from .online_library_manager import OnlineLibraryManager
                    ol_manager = OnlineLibraryManager(DOWNLOADS_PATH, None)
                    folder_name = ol_manager.get_allanime_folder_name(show_id)
                    path = os.path.join(DOWNLOADS_PATH, folder_name)
                    if os.path.isdir(path):
                        base_dir = path
                    else:
                        # 2. original show_id (old way)
                        safe_id = re.sub(r'[/\\:*?"<>|]', '_', show_id)
                        base_dir = os.path.join(DOWNLOADS_PATH, safe_id)
                else:
                    safe_id = re.sub(r'[/\\:*?"<>|]', '_', show_id)
                    base_dir = os.path.join(DOWNLOADS_PATH, safe_id)
            
            # Try original filename
            path = os.path.join(base_dir, filename)
            if os.path.exists(path):
                return path if filename not in self.active_tasks else None
            
            # Try with .mp4 if it doesn't have it
            if not any(filename.lower().endswith(ext) for ext in ['.mp4', '.mkv', '.avi', '.ts', '.mov']):
                path_mp4 = path + ".mp4"
                if os.path.exists(path_mp4):
                    return path_mp4 if filename not in self.active_tasks else None
            
            # Scan directory for any video file - useful for torrents/magnets
            if os.path.isdir(base_dir):
                video_extensions = ['.mp4', '.mkv', '.avi', '.ts', '.mov']
                
                # If no ep_no provided, try to extract it from standard formatting
                req_ep = str(ep_no) if ep_no is not None else None
                if not req_ep:
                    ep_match = re.search(r"- Ep (\d+(?:\.\d+)?)", filename)
                    req_ep = ep_match.group(1) if ep_match else None
                
                max_size = -1
                best_file = None
                
                for root, dirs, files in os.walk(base_dir):
                    for f in files:
                        if any(f.lower().endswith(ext) for ext in video_extensions):
                            # If we are looking for a specific episode, try to ensure the file matches it
                            if req_ep:
                                # Clean up req_ep to avoid float artifacts like "6.0" when it should be "6"
                                if req_ep.endswith(".0"): req_ep = req_ep[:-2]
                                
                                # Look for padding like " 05 ", " - 5 ", "_05_", etc.
                                # A simple approach: pad the requested episode or just search for it surrounded by non-digits
                                padded_ep = req_ep.zfill(2)
                                if not re.search(rf"(?:^|[^a-zA-Z0-9])0*{req_ep}(?:\.[0-9]+)?(?:[^a-zA-Z0-9]|$)", f):
                                    continue # Skip if episode number doesn't clearly match
                                    
                            f_path = os.path.join(root, f)
                            f_size = os.path.getsize(f_path)
                            if f_size > max_size:
                                max_size = f_size
                                best_file = f_path
                                
                if best_file:
                    return best_file
                    
        # 2. Check in base folder (Old way / Migration fallback)
        path = os.path.join(DOWNLOADS_PATH, filename)
        if os.path.exists(path):
            if filename in self.active_tasks:
                return None
            return path
            
        return None

    def get_all_tasks(self):
        """Returns all tasks (active, pending, history) for UI display."""
        return {
            "active": self.active_tasks.keys(),
            "pending": [t[1] for t in self.pending_tasks],
            "history": self.history,
            "states": self.task_states
        }

    def clear_history(self):
        self.history = []
        if self.db:
            asyncio.create_task(self.db.clear_download_history())
        # Also clean up task_states for finished/failed tasks
        to_remove = [fn for fn, state in self.task_states.items() 
                     if state["status"] in ["Finished", "Failed", "Cancelled"]]
        for fn in to_remove:
            del self.task_states[fn]
