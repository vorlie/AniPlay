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
        output_path = os.path.join(DOWNLOADS_PATH, self.filename)
        # Use ffmpeg to download. -y to overwrite, -c copy to avoid re-encoding if possible
        cmd = ["ffmpeg", "-y"]
        if self.referrer:
            cmd.extend(["-headers", f"Referer: {self.referrer}\r\n"])
        
        cmd.extend(["-i", self.url, "-stats", "-c", "copy", "-bsf:a", "aac_adtstoasc", output_path])
        
        logger.info(f"Starting download: {' '.join(cmd)}")
        
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
            # Use read(1024) and split by \r or \n to catch all progress updates
            buffer = ""
            while True:
                chunk = await self.process.stderr.read(1024)
                if not chunk:
                    break
                
                buffer += chunk.decode(errors='replace')
                # Progress updates in ffmpeg often use \r to overwrite the line
                lines = re.split(r'[\r\n]+', buffer)
                # Keep the last partial line in the buffer
                if buffer and buffer[-1] not in ['\r', '\n']:
                    buffer = lines.pop()
                else:
                    buffer = ""
                
                for line_str in lines:
                    line_str = line_str.strip()
                    if not line_str: continue
                    
                    # Try to find duration: Duration: 00:23:40.12
                    if not duration:
                        dur_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", line_str)
                        if dur_match:
                            h, m, s = map(float, dur_match.groups())
                            duration = h * 3600 + m * 60 + s
                            logger.info(f"Detected download duration: {duration}s")
                    
                    # Try to find current time: time=00:00:05.12
                    time_match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line_str)
                    speed_match = re.search(r"speed=\s*([\d.]+[xX]?)", line_str)
                    
                    if time_match:
                        speed_str = speed_match.group(1) if speed_match else "0.0x"
                        # Extract the numeric part of speed (e.g., 54.3 from 54.3x)
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
                            
                            # Calculate ETA
                            if speed_val > 0:
                                remaining_seconds = (duration - current_time) / speed_val
                                m_rem, s_rem = divmod(int(remaining_seconds), 60)
                                h_rem, m_rem = divmod(m_rem, 60)
                                if h_rem > 0:
                                    eta_str = f"{h_rem}:{m_rem:02d}:{s_rem:02d}"
                                else:
                                    eta_str = f"{m_rem}:{s_rem:02d}"
                            
                            self.progress_updated.emit(self.filename, min(progress, 100.0), speed_str, eta_str, elapsed_str)
                        else:
                            # If no duration yet, just emit 0% with speed/time
                            self.progress_updated.emit(self.filename, 0.0, f"{speed_str} @ {int(current_time)}s", eta_str, elapsed_str)

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
            except:
                pass

class DownloadManager(QObject):
    task_progress = pyqtSignal(str, float, str, str, str)
    task_finished = pyqtSignal(str, bool, str, dict)
    queue_updated = pyqtSignal(int) # Number of pending tasks
    
    def __init__(self):
        super().__init__()
        self.active_tasks = {} # filename -> DownloadTask
        self.pending_tasks = [] # list of (url, filename, referrer, metadata)
        self.max_concurrent = 1

    def start_download(self, url, filename, referrer=None, metadata=None):
        """Adds a download to the queue."""
        # Ensure filename is safe and has .mp4 extension
        if not filename.endswith(".mp4"):
            filename += ".mp4"

        if filename in self.active_tasks or any(t[1] == filename for t in self.pending_tasks):
            logger.warning(f"Download already in progress or queued for {filename}")
            return False
            
        self.pending_tasks.append((url, filename, referrer, metadata))
        self.queue_updated.emit(len(self.pending_tasks))
        
        self._process_queue()
        return True

    def _process_queue(self):
        """Starts next tasks if below concurrency limit."""
        while len(self.active_tasks) < self.max_concurrent and self.pending_tasks:
            url, filename, referrer, metadata = self.pending_tasks.pop(0)
            self.queue_updated.emit(len(self.pending_tasks))
            
            task = DownloadTask(url, filename, referrer, metadata)
            task.progress_updated.connect(self.task_progress.emit)
            task.finished.connect(self._on_task_finished)
            
            self.active_tasks[filename] = task
            asyncio.create_task(task.run())

    def _on_task_finished(self, filename, success, message, metadata):
        if filename in self.active_tasks:
            del self.active_tasks[filename]
        
        self.task_finished.emit(filename, success, message, metadata)
        # Start next in queue
        self._process_queue()

    def is_downloading(self, filename):
        if not filename.endswith(".mp4"):
            filename += ".mp4"
        return filename in self.active_tasks or any(t[1] == filename for t in self.pending_tasks)

    def cancel_download(self, filename):
        if not filename.endswith(".mp4"):
            filename += ".mp4"

        # Check pending
        for i, t in enumerate(self.pending_tasks):
            if t[1] == filename:
                self.pending_tasks.pop(i)
                self.queue_updated.emit(len(self.pending_tasks))
                return True

        # Check active
        if filename in self.active_tasks:
            self.active_tasks[filename].cancel()
            return True
        return False

    def get_local_path(self, filename):
        if not filename.endswith(".mp4"):
            filename += ".mp4"
        path = os.path.join(DOWNLOADS_PATH, filename)
        if os.path.exists(path):
            # Also check if it's currently downloading
            if filename in self.active_tasks:
                return None
            return path
        return None
