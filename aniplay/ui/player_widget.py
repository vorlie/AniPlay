import os
import subprocess
import time
import base64
import urllib.request
import re
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
import mpv

from .vlc_window import VlcPlayerWindow

try:
    import vlc
except ImportError:
    vlc = None

from ..utils.logger import get_logger
logger = get_logger(__name__)

class PlayerWidget(QWidget):
    # Signals
    playback_started = pyqtSignal(str)
    playback_paused = pyqtSignal(float)
    playback_resumed = pyqtSignal()
    progress_updated = pyqtSignal(float, float)
    playback_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(15, 12, 15, 12)
        self.layout.setSpacing(20)
        
        self.setStyleSheet("""
            PlayerWidget {
                background-color: rgba(0, 0, 0, 0.2);
                border-radius: 10px;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
        self.status_icon = QLabel("📺")
        self.status_icon.setStyleSheet("font-size: 28px;")
        
        self.info_label = QLabel("Ready to play")
        self.info_label.setStyleSheet("""
            font-weight: bold; 
            font-size: 15px;
            color: rgba(255, 255, 255, 0.8);
        """)
        
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("""
            font-family: 'Consolas', monospace;
            font-size: 14px;
            font-weight: bold;
            color: rgba(255, 255, 255, 0.7);
            padding: 5px 15px;
            background-color: rgba(0, 0, 0, 0.3);
            border-radius: 6px;
        """)

        self.layout.addWidget(self.status_icon)
        self.layout.addWidget(self.info_label, 1) 
        self.layout.addWidget(self.time_label)

        self.player_type = "mpv"
        self.player = None
        self.external_process = None
        self.vlc_window = None
        self._current_time = 0
        self._duration = 0
        self.is_paused = False
        
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_progress)
        self.poll_timer.setInterval(1000)

    def load_video(self, path: str, start_time: float = 0):
        logger.info(f"Loading video: {path} (Start time: {start_time})")
        self.shutdown() 
        
        if self.player_type == "mpv":
            self._load_mpv(path, start_time)
        elif self.player_type == "vlc":
            self._load_vlc(path, start_time)
        elif self.player_type == "embedded_vlc":
            self._load_embedded_vlc(path, start_time)

    def _find_executable(self, name: str) -> str:
        """Find executable in PATH or common Windows locations."""
        # 1. Check PATH
        import shutil
        path = shutil.which(name)
        if path:
            return path
            
        # 2. Check current directory
        local_path = os.path.join(os.getcwd(), f"{name}.exe")
        if os.path.exists(local_path):
            return local_path
            
        # 3. Check common Windows paths
        fallbacks = []
        if name == "vlc":
            fallbacks = [
                r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
            ]
        elif name == "mpv":
            fallbacks = [
                r"C:\Program Files\mpv\mpv.exe",
                r"C:\mpv\mpv.exe"
            ]
            
        for fb in fallbacks:
            if os.path.exists(fb):
                return fb
                
        return name # Return original name and hope for the best

    def _load_mpv(self, path, start_time):
        exe = self._find_executable("mpv")
        logger.debug(f"Using mpv executable: {exe}")
        
        # IPC socket path (randomish name)
        self.ipc_path = f"\\\\.\\pipe\\aniplay_mpv_{int(time.time())}"
        
        cmd = [
            exe,
            path,
            f"--start={start_time}",
            f"--input-ipc-server={self.ipc_path}",
            "--force-window=yes",
            "--title=AniPlay - Playing"
        ]
        
        try:
            self.external_process = subprocess.Popen(cmd)
            self.status_icon.setText("🎬")
            self.info_label.setText(f"Playing in MPV: {os.path.basename(path)}")
            self.setStyleSheet("""
                PlayerWidget {
                    background-color: rgba(0, 200, 83, 0.15);
                    border-radius: 10px;
                    border-top: 2px solid #00c853;
                }
            """)
            QTimer.singleShot(1000, self._connect_ipc) # Longer delay for external
            self.playback_started.emit(os.path.basename(path))
        except FileNotFoundError:
            self.info_label.setText(f"Error: '{exe}' not found.")

    def _load_vlc(self, path, start_time):
        exe = self._find_executable("vlc")
        logger.debug(f"Using vlc executable: {exe}")
        
        # VLC start time is in seconds
        self.vlc_password = "aniplay"
        # Standard VLC argument order: [exe, options, path]
        cmd = [
            exe,
            "--extraintf", "http",
            "--http-password", self.vlc_password,
            "--start-time", str(int(start_time)),
            path
        ]
        
        try:
            self.external_process = subprocess.Popen(cmd)
            self.status_icon.setText("🎬")
            self.info_label.setText(f"Playing in VLC: {os.path.basename(path)}")
            self.setStyleSheet("""
                PlayerWidget {
                    background-color: rgba(0, 200, 83, 0.15);
                    border-radius: 10px;
                    border-top: 2px solid #00c853;
                }
            """)
            self.playback_started.emit(os.path.basename(path))
            self.poll_timer.start()
        except FileNotFoundError:
            self.info_label.setText(f"Error: '{exe}' not found.")

    def _load_embedded_vlc(self, path, start_time):
        if not vlc:
            self.info_label.setText("Error: python-vlc not installed")
            return

        try:
            self.vlc_window = VlcPlayerWindow()
            self.vlc_window.progress_updated.connect(self._on_vlc_progress)
            self.vlc_window.playback_paused.connect(self._on_pause)
            self.vlc_window.playback_resumed.connect(self._on_resume)
            self.vlc_window.playback_finished.connect(self.playback_finished.emit)
            self.vlc_window.window_closed.connect(self.shutdown)
            
            self.vlc_window.show()
            self.vlc_window.play_path(path, start_time)

            self.status_icon.setText("🎬")
            self.info_label.setText(f"Playing (VLC Window): {os.path.basename(path)}")
            self.setStyleSheet("""
                PlayerWidget {
                    background-color: rgba(0, 200, 83, 0.15);
                    border-radius: 10px;
                    border-top: 2px solid #00c853;
                }
            """)
            self.playback_started.emit(os.path.basename(path))
            
        except Exception as e:
            logger.error(f"Failed to load embedded VLC: {e}", exc_info=True)
            self.info_label.setText(f"VLC Error: {e}")

    def _on_vlc_progress(self, current, duration):
        self._current_time = current
        self._duration = duration
        self.progress_updated.emit(current, duration)
        
        cur = self._format_time(current)
        tot = self._format_time(duration)
        self.time_label.setText(f"{cur} / {tot}")

    def _on_pause(self, timestamp):
        logger.info(f"Playback paused at {timestamp}")
        self.is_paused = True
        self.playback_paused.emit(timestamp)

    def _on_resume(self):
        logger.info("Playback resumed")
        self.is_paused = False
        self.playback_resumed.emit()

    def _connect_ipc(self):
        try:
            # Connect to the external MPV via its IPC pipe 
            # (DOESNT WORK LOL, MPV DOESNT HAVE THATTTTT)
            self.player = mpv.MPV(start_mpv=False, ipc_socket=self.ipc_path)
            self.poll_timer.start()
        except Exception as e:
            print(f"Failed to connect to MPV IPC: {e}")

    def _poll_progress(self):
        if self.player_type == "mpv":
            self._poll_mpv()
        elif self.player_type == "vlc":
            self._poll_vlc()

    def _poll_mpv(self):
        if not self.player:
            return
            
        try:
            self._current_time = self.player.time_pos or 0
            self._duration = self.player.duration or 0
            
            if self._current_time > 0:
                self.progress_updated.emit(self._current_time, self._duration)
                
            cur = self._format_time(self._current_time)
            tot = self._format_time(self._duration)
            self.time_label.setText(f"{cur} / {tot}")
        except (AttributeError, BrokenPipeError, ConnectionRefusedError, mpv.MPVError):
            self.shutdown()
            self.playback_finished.emit()

    def _poll_vlc(self):
        # Check if process is still running
        if self.external_process and self.external_process.poll() is not None:
            self.shutdown()
            self.playback_finished.emit()
            return

        # Poll VLC HTTP interface
        url = "http://localhost:8080/requests/status.xml"
        req = urllib.request.Request(url)
        auth = base64.b64encode(f":{self.vlc_password}".encode()).decode()
        req.add_header("Authorization", f"Basic {auth}")
        
        try:
            with urllib.request.urlopen(req, timeout=1) as response:
                content = response.read().decode('utf-8')
                
                # Basic parsing using regex to avoid heavy XML libs
                time_match = re.search(r"<time>(\d+)</time>", content)
                length_match = re.search(r"<length>(\d+)</length>", content)
                
                if time_match and length_match:
                    self._current_time = float(time_match.group(1))
                    self._duration = float(length_match.group(1))
                    
                    self.progress_updated.emit(self._current_time, self._duration)
                    
                    cur = self._format_time(self._current_time)
                    tot = self._format_time(self._duration)
                    self.time_label.setText(f"{cur} / {tot}")
        except Exception:
            pass

    def shutdown(self):
        logger.debug("Shutting down player")
        self.poll_timer.stop()
        self.is_paused = False
        
        if self.vlc_window:
            # Prevent recursion
            win = self.vlc_window
            self.vlc_window = None
            win.close()
            
        if self.player:
            self.player = None
            
        if self.external_process:
            self.external_process = None
            
        self.status_icon.setText("📺")
        self.info_label.setText("Select an episode to play")
        self.time_label.setText("00:00 / 00:00")
        self.setStyleSheet("""
            PlayerWidget {
                background-color: rgba(0, 0, 0, 0.2);
                border-radius: 10px;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)

    def _format_time(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def closeEvent(self, event):
        self.shutdown()
        event.accept()
