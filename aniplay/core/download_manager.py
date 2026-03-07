import asyncio
import os
import subprocess
import re
from PyQt6.QtCore import QObject, pyqtSignal
from ..utils.logger import get_logger
from ..config import DOWNLOADS_PATH

logger = get_logger(__name__)

class DownloadTask(QObject):
    progress_updated = pyqtSignal(str, float) # filename, percentage
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
        
        cmd.extend(["-i", self.url, "-c", "copy", "-bsf:a", "aac_adtstoasc", output_path])
        
        logger.info(f"Starting download: {' '.join(cmd)}")
        
        try:
            # We use create_subprocess_exec to monitor stderr for duration/time to calculate progress
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            duration = 0
            async for line in self.process.stderr:
                line_str = line.decode().strip()
                
                # Try to find duration: Duration: 00:23:40.12
                if not duration:
                    dur_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", line_str)
                    if dur_match:
                        h, m, s = map(float, dur_match.groups())
                        duration = h * 3600 + m * 60 + s
                
                # Try to find current time: time=00:00:05.12
                time_match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line_str)
                if time_match and duration > 0:
                    h, m, s = map(float, time_match.groups())
                    current_time = h * 3600 + m * 60 + s
                    progress = (current_time / duration) * 100
                    self.progress_updated.emit(self.filename, min(progress, 100.0))

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
    task_progress = pyqtSignal(str, float)
    task_finished = pyqtSignal(str, bool, str, dict)
    
    def __init__(self):
        super().__init__()
        self.active_tasks = {} # filename -> DownloadTask

    def start_download(self, url, filename, referrer=None, metadata=None):
        if filename in self.active_tasks:
            logger.warning(f"Download already in progress for {filename}")
            return False
            
        # Ensure filename is safe and has .mp4 extension
        if not filename.endswith(".mp4"):
            filename += ".mp4"
            
        task = DownloadTask(url, filename, referrer, metadata)
        task.progress_updated.connect(self.task_progress.emit)
        task.finished.connect(self._on_task_finished)
        
        self.active_tasks[filename] = task
        asyncio.create_task(task.run())
        return True

    def _on_task_finished(self, filename, success, message, metadata):
        if filename in self.active_tasks:
            del self.active_tasks[filename]
        self.task_finished.emit(filename, success, message, metadata)

    def is_downloading(self, filename):
        if not filename.endswith(".mp4"):
            filename += ".mp4"
        return filename in self.active_tasks

    def cancel_download(self, filename):
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
