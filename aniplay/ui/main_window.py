import sys
import ctypes
import os
from PyQt6.QtWidgets import QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QMessageBox, QComboBox, QApplication
from PyQt6.QtCore import Qt
import qasync
import asyncio

from .series_widget import SeriesWidget
from .episode_widget import EpisodeWidget
from .player_widget import PlayerWidget
from ..database.db import DatabaseManager
from ..database.models import Series, Episode, WatchProgress
from ..core.library_manager import LibraryManager
from ..core.library_manager import LibraryManager
from ..core.discord_manager import DiscordManager
from ..config import DEFAULT_LIBRARY_PATH, PREFERRED_PLAYER

class MainWindow(QMainWindow):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.setWindowTitle("AniPlay")
        self.resize(1280, 850)
        self.setStyleSheet("""
            QMainWindow, QWidget#centralWidget {
                background-color: #121212;
                color: #ffffff;
            }
            QSplitter::handle {
                background-color: #333;
            }
            QScrollBar:vertical {
                border: none;
                background: #1a1a1a;
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #333;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #444;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.db = db_manager
        self.library = LibraryManager(self.db)
        self.discord = DiscordManager()
        self.current_episode = None
        self.current_series = None

        self.setup_ui()

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # 1. Player Panel (Bottom-most logic, but created first to allow syncing)
        self.player_widget = PlayerWidget()
        self.player_widget.progress_updated.connect(self.on_progress_updated)
        self.player_widget.playback_paused.connect(self.save_progress)
        self.player_widget.playback_finished.connect(self.on_playback_finished)
        
        # 2. Top Bar: Actions
        self.top_bar = QHBoxLayout()
        
        self.scan_btn = QPushButton("Scan Library")
        self.scan_btn.setFixedHeight(40)
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d5afe;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #536dfe;
            }
        """)
        self.scan_btn.clicked.connect(self.scan_library)
        
        self.mount_btn = QPushButton("Mount Drive (Admin)")
        self.mount_btn.setFixedHeight(40)
        self.mount_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #ef5350;
            }
        """)
        self.mount_btn.clicked.connect(self.mount_drive)
        
        self.player_selector = QComboBox()
        self.player_selector.addItems(["mpv", "vlc"])
        self.player_selector.currentTextChanged.connect(self.on_player_changed)
        self.player_selector.setCurrentText(PREFERRED_PLAYER)
        self.player_selector.setFixedHeight(40)
        self.player_selector.setFixedWidth(100)
        self.player_selector.setStyleSheet("""
            QComboBox {
                background-color: #2d2d2d;
                color: white;
                border-radius: 5px;
                padding-left: 10px;
            }
        """)
        
        self.top_bar.addWidget(self.scan_btn)
        self.top_bar.addWidget(self.mount_btn)
        self.top_bar.addWidget(self.player_selector)
        self.top_bar.addStretch()
        
        # 3. Middle: Library Splitter (Horizontal)
        self.library_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.series_widget = SeriesWidget()
        self.series_widget.series_selected.connect(self.on_series_selected)
        self.series_widget.series_watched_toggled.connect(self.on_series_watched_toggled)
        self.series_widget.poster_change_requested.connect(self.on_poster_change_requested)
        
        self.episode_widget = EpisodeWidget()
        self.episode_widget.episode_selected.connect(self.on_episode_selected)
        self.episode_widget.episode_watched_toggled.connect(self.on_episode_watched_toggled)
        
        self.library_splitter.addWidget(self.series_widget)
        self.library_splitter.addWidget(self.episode_widget)
        self.library_splitter.setSizes([400, 800])
        
        # Assemble Main Layout
        self.main_layout.addLayout(self.top_bar)
        self.main_layout.addWidget(self.library_splitter, 1) # Takes majority of space
        self.main_layout.addWidget(self.player_widget)

        # Final Sync (everything now exists)
        self.on_player_changed(PREFERRED_PLAYER)

    async def load_initial_data(self):
        series = await self.library.get_all_series()
        self.series_widget.set_series(series)

    @qasync.asyncSlot()
    async def scan_library(self, checked=False):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("Scanning...")
        await self.library.scan_library()
        series = await self.library.get_all_series()
        self.series_widget.set_series(series)
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Scan Library")

    @qasync.asyncSlot(object)
    async def on_series_selected(self, series):
        self.current_series = series
        episodes = await self.library.get_episodes(series.id)
        
        # Fetch progress for all episodes in this series
        progress_map = {}
        for ep in episodes:
            progress = await self.db.get_progress(ep.id)
            if progress:
                progress_map[ep.id] = progress
                
        self.episode_widget.set_episodes(episodes, progress_map)

    @qasync.asyncSlot(object, bool)
    async def on_series_watched_toggled(self, series, watched):
        await self.db.mark_series_watched(series.id, watched)
        # Refresh the current episode list if this series is selected
        if self.current_series and self.current_series.id == series.id:
            await self.on_series_selected(series)

    @qasync.asyncSlot(object, bool)
    async def on_episode_watched_toggled(self, episode, watched):
        await self.db.mark_episode_watched(episode.id, watched)
        # Refresh current view
        if self.current_series:
            await self.on_series_selected(self.current_series)

    @qasync.asyncSlot(object)
    async def on_poster_change_requested(self, series):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Poster", series.path, 
            "Images (*.jpg *.jpeg *.png *.webp)"
        )
        if file_path:
            await self.db.update_series_poster(series.id, file_path)
            # Refresh library view
            series_list = await self.library.get_all_series()
            self.series_widget.set_series(series_list)

    @qasync.asyncSlot(object)
    async def on_episode_selected(self, episode):
        self.current_episode = episode
        
        # Update Discord RPC
        if self.current_series:
            await self.discord.update_presence(
                series=self.current_series.name,
                episode=episode.filename,
                player=self.player_widget.player_type
            )
            
        progress = await self.db.get_progress(episode.id)
        start_time = progress.timestamp if progress else 0
        self.player_widget.load_video(episode.path, start_time)

    @qasync.asyncSlot(float, float)
    async def on_progress_updated(self, current, total):
        await self.save_progress(current)

    @qasync.asyncSlot(float)
    async def save_progress(self, timestamp=None):
        if not self.current_episode:
            return
        
        if timestamp is None:
            timestamp = self.player_widget._current_time
            
        is_completed = False
        if self.player_widget._duration > 0:
            if timestamp / self.player_widget._duration > 0.9:
                is_completed = True
        
        progress = WatchProgress(
            episode_id=self.current_episode.id,
            timestamp=timestamp,
            completed=is_completed
        )
        await self.db.update_progress(progress)

    @qasync.asyncSlot()
    async def on_playback_finished(self):
        if self.current_episode:
            await self.save_progress(timestamp=self.player_widget._duration)
        # Handle auto-play next?

    def on_player_changed(self, player_type):
        self.player_widget.player_type = player_type
        self.player_widget.shutdown()

    def mount_drive(self):
        bat_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../mountdrive.bat"))
        if not os.path.exists(bat_path):
            # Fallback to current dir if not in package structure
            bat_path = os.path.abspath("mountdrive.bat")
            
        if not os.path.exists(bat_path):
            QMessageBox.critical(self, "Error", f"mountdrive.bat not found at {bat_path}")
            return

        try:
            # Execute as Admin
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f"/c \"{bat_path}\"", None, 1)
            QMessageBox.information(self, "Mounting", "Executing mount script as Administrator...")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to execute mount script: {e}")

    def closeEvent(self, event):
        self.player_widget.shutdown()
        
        # Async cleanup (fire and forget in sync closeEvent)
        asyncio.create_task(self.discord.clear())
        asyncio.create_task(self.discord.shutdown())
        
        app = QApplication.instance()
        if app:
            app.quit()
        event.accept()
