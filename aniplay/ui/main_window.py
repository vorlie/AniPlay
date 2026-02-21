import sys
import ctypes
import os
from PyQt6.QtWidgets import QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QMessageBox, QComboBox, QApplication, QMenu, QCheckBox
from PyQt6.QtCore import Qt
import qasync
import asyncio

from .series_widget import SeriesWidget
from .episode_widget import EpisodeWidget
from .player_widget import PlayerWidget
from ..database.db import DatabaseManager
from ..database.models import Series, Episode, WatchProgress
from ..core.library_manager import LibraryManager
from ..core.discord_manager import DiscordManager
from .metadata_manager import MetadataManager
from ..config import DEFAULT_LIBRARY_PATH, PREFERRED_PLAYER
from ..utils.logger import get_logger

logger = get_logger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.setWindowTitle("AniPlay")
        self.resize(1280, 850)
        self.showMaximized()
        # Theme will be handled by qdarktheme
        self.setStyleSheet("")

        self.db = db_manager
        self.library = LibraryManager(self.db)
        self.discord = DiscordManager()
        self.current_episode = None
        self.current_series = None

        self.setup_ui()
        logger.info("MainWindow initialized")

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(15, 15, 15, 15)

        # 1. Player Panel (Bottom-most logic, but created first to allow syncing)
        self.player_widget = PlayerWidget()
        self.player_widget.progress_updated.connect(self.on_progress_updated)
        self.player_widget.playback_paused.connect(self.on_playback_paused)
        self.player_widget.playback_resumed.connect(self.on_playback_resumed)
        self.player_widget.playback_finished.connect(self.on_playback_finished)
        
        # 2. Top Bar: Actions
        self.top_bar = QHBoxLayout()
        
        # Scan Button with Menu
        self.scan_btn = QPushButton("🔄 Quick Sync")
        self.scan_btn.setFixedHeight(40)
        self.scan_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 10pt;
                padding: 0 20px;
                border-radius: 8px;
                background-color: #2196f3;
                color: white;
            }
            QPushButton::menu-indicator { image: none; }
        """)
        
        scan_menu = QMenu(self)
        scan_menu.addAction("Quick Sync (Incremental)", lambda: self.run_scan(full_scan=False))
        scan_menu.addAction("Full Re-scan (Overwrite Titles)", lambda: self.run_scan(full_scan=True))
        self.scan_btn.setMenu(scan_menu)
        self.scan_btn.clicked.connect(lambda: self.run_scan(full_scan=False))
        
        self.mount_btn = QPushButton("🔒 Mount Drive")
        self.mount_btn.setFixedHeight(40)
        self.mount_btn.setStyleSheet("""
            QPushButton {
                color: #f44336;
                font-weight: bold;
                font-size: 10pt;
                padding: 0 20px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: rgba(244, 67, 54, 0.1);
            }
        """)
        self.mount_btn.clicked.connect(self.mount_drive)
        
        self.player_selector = QComboBox()
        self.player_selector.addItems(["mpv", "vlc", "embedded_vlc"])
        self.player_selector.currentTextChanged.connect(self.on_player_changed)
        self.player_selector.setCurrentText(PREFERRED_PLAYER)
        self.player_selector.setFixedHeight(40)
        self.player_selector.setFixedWidth(150)
        self.player_selector.setStyleSheet("""
            QComboBox {
                padding: 8px 15px;
                border-radius: 8px;
                font-size: 10pt;
            }
        """)
        
        self.top_bar.addWidget(self.scan_btn)
        self.top_bar.addSpacing(10)
        
        self.meta_btn = QPushButton("📝 Metadata")
        self.meta_btn.setFixedHeight(40)
        self.meta_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 10pt;
                padding: 0 20px;
                border-radius: 8px;
            }
        """)
        self.meta_btn.clicked.connect(self.open_metadata_manager)
        self.top_bar.addWidget(self.meta_btn)
        self.top_bar.addSpacing(15)

        # NSFW Toggle
        self.nsfw_toggle = QCheckBox("Watching NSFW? Hide")
        self.nsfw_toggle.setStyleSheet("""
            QCheckBox {
                color: rgba(255, 255, 255, 0.7);
                font-size: 10pt;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        self.nsfw_toggle.stateChanged.connect(lambda: asyncio.create_task(self.update_discord_rpc()))
        self.top_bar.addWidget(self.nsfw_toggle)
        self.top_bar.addSpacing(10)

        self.top_bar.addWidget(self.mount_btn)
        self.top_bar.addSpacing(10)
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
        self.library_splitter.setSizes([350, 850])
        self.library_splitter.setHandleWidth(1)
        
        # Assemble Main Layout
        self.main_layout.addLayout(self.top_bar)
        self.main_layout.addWidget(self.library_splitter, 1) # Takes majority of space
        self.main_layout.addWidget(self.player_widget)

        # Final Sync (everything now exists)
        self.on_player_changed(PREFERRED_PLAYER)
        logger.debug("UI setup complete")

    async def load_initial_data(self):
        logger.info("Loading initial data...")
        series = await self.library.get_all_series()
        self.series_widget.set_series(series)

    @qasync.asyncSlot()
    async def run_scan(self, full_scan=False):
        try:
            self.scan_btn.setEnabled(False)
            logger.info(f"Starting library sync (full_scan={full_scan})")
            await self.library.scan_library(full_scan=full_scan)
            
            # Refresh library view
            logger.debug("Refreshing series list after scan")
            series_list = await self.library.get_all_series()
            self.series_widget.set_series(series_list)
            
            self.scan_btn.setEnabled(True)
            self.scan_btn.setText("🔄 Quick Sync")
            QMessageBox.information(self, "Scan Complete", "Library sync finished!")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Library scan failed: {e}")
            self.scan_btn.setEnabled(True)
            self.scan_btn.setText("🔄 Quick Sync")

    @qasync.asyncSlot()
    async def scan_library(self, checked=False):
        # Compatibility/Legacy
        await self.run_scan(full_scan=False)

    @qasync.asyncSlot(object)
    async def on_series_selected(self, series):
        logger.info(f"Series selected: {series.name}")
        self.current_series = series
        episodes = await self.library.get_episodes(series.id)
        
        # Update selection info with correct episode count
        self.series_widget.selection_info.update_info(series.name, len(episodes), series.size_bytes)
        
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
        logger.info(f"Episode selected: {episode.filename}")
        self.current_episode = episode
        
        progress = await self.db.get_progress(episode.id)
        start_time = progress.timestamp if progress else 0

        # Update Discord RPC
        await self.update_discord_rpc(episode, start_time)
            
        self.player_widget.load_video(episode.path, start_time)

    async def update_discord_rpc(self, episode=None, timestamp=None):
        if not episode:
            episode = self.current_episode
        if not episode or not self.current_series:
            return
            
        if timestamp is None:
            timestamp = self.player_widget._current_time

        display_name = episode.title if episode.title else episode.filename
        
        # Privacy/NSFW logic
        is_safe_mode = self.nsfw_toggle.isChecked()
        series_name = self.current_series.name if not is_safe_mode else "Secret Series"
        episode_display = display_name if not is_safe_mode else "Classified Episode"
        thumb_path = self.current_series.thumbnail_path if not is_safe_mode else None
        cached_url = self.current_series.rpc_image_url if not is_safe_mode else None

        # Use cached URL if available
        rpc_url = await self.discord.update_presence(
            series=series_name,
            episode=episode_display,
            player=self.player_widget.player_type,
            thumbnail_path=thumb_path,
            cached_thumbnail_url=cached_url,
            duration=episode.duration,
            start_offset=timestamp,
            is_paused=self.player_widget.is_paused
        )
        
        # If we got a new URL (upload happened), save it to DB (only if not in safe mode)
        if not is_safe_mode and rpc_url and rpc_url != self.current_series.rpc_image_url:
            logger.info(f"Caching new RPC image URL for series: {self.current_series.name}")
            self.current_series.rpc_image_url = rpc_url
            await self.db.update_series_rpc_url(self.current_series.id, rpc_url)

    @qasync.asyncSlot(float, float)
    async def on_progress_updated(self, current, total):
        await self.save_progress(current)

    @qasync.asyncSlot(float)
    async def on_playback_paused(self, timestamp):
        await self.save_progress(timestamp)
        await self.update_discord_rpc(timestamp=timestamp)

    @qasync.asyncSlot()
    async def on_playback_resumed(self):
        await self.update_discord_rpc()

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
            
        # 2. Try to play the next one automatically
        await self.play_next_episode()

    async def play_next_episode(self):
        if not self.current_series:
            return

        # Get the list of episodes
        episodes = await self.library.get_episodes(self.current_series.id)
        
        # Find the index of the current episode
        current_idx = -1
        for i, ep in enumerate(episodes):
            if ep.id == self.current_episode.id:
                current_idx = i
                break
                
        # If there's a next one, select it
        if current_idx != -1 and current_idx + 1 < len(episodes):
            next_ep = episodes[current_idx + 1]
            logger.info(f"Auto-advancing to: {next_ep.filename}")
            await self.on_episode_selected(next_ep)
        else:
            logger.info("End of series reached.")
            # self.player_widget.shutdown()

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

    def open_metadata_manager(self):
        self.meta_window = MetadataManager(self.db, self)
        self.meta_window.show()

    def closeEvent(self, event):
        self.player_widget.shutdown()
        
        # Async cleanup (fire and forget in sync closeEvent)
        asyncio.create_task(self.discord.clear())
        asyncio.create_task(self.discord.shutdown())
        
        app = QApplication.instance()
        if app:
            app.quit()
        event.accept()
