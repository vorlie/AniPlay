import sys
import ctypes
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout, 
    QPushButton, QFileDialog, QMessageBox, QComboBox, 
    QApplication, QMenu, QCheckBox, QTabWidget
)
from PyQt6.QtCore import Qt
import qasync
import asyncio

from .series_widget import SeriesWidget
from .episode_widget import EpisodeWidget
from .player_widget import PlayerWidget
from .online_search_widget import OnlineSearchWidget
from ..core.download_manager import DownloadManager
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
        self.download_manager = DownloadManager()
        self.discord = DiscordManager()
        
        # Connect Download Signals
        self.download_manager.task_progress.connect(self.on_download_progress)
        self.download_manager.task_finished.connect(self.on_download_finished)

        self.current_episode = None
        self.current_series = None
        self.current_online_show = None # {id, name, thumbnail}
        self.current_online_episode = None # number

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
        
        # 4. Content Tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #333;
                border-radius: 4px;
                background-color: #121212;
            }
            QTabBar::tab {
                background-color: #1e1e1e;
                color: #888;
                padding: 12px 30px;
                margin-right: 5px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
                font-size: 10pt;
            }
            QTabBar::tab:selected {
                background-color: #3d5afe;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #2a2a2a;
            }
        """)
        
        self.online_widget = OnlineSearchWidget(self.player_widget, self.db, self, self.download_manager)
        
        self.tabs.addTab(self.library_splitter, "📁 Local Library")
        self.tabs.addTab(self.online_widget, "🌐 Online Search")
        
        # Assemble Main Layout
        self.main_layout.addLayout(self.top_bar)
        self.main_layout.addWidget(self.tabs, 1) # Takes majority of space
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
        self.current_online_show = None
        self.current_online_episode = None
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
        self.current_online_show = None
        self.current_online_episode = None
        
        progress = await self.db.get_progress(episode.id)
        start_time = progress.timestamp if progress else 0

        # Update Discord RPC
        await self.update_discord_rpc(episode, start_time)
            
        self.player_widget.load_video(episode.path, start_time)

    async def update_discord_rpc(self, episode=None, timestamp=None, online_data=None):
        """
        Updates Discord Presence. 
        If online_data is provided, it's an online stream: {show_id, show_name, ep_no, thumbnail_url}
        """
        if online_data:
            self.current_episode = None
            self.current_series = None
            self.current_online_show = {
                "id": online_data["show_id"],
                "name": online_data["show_name"],
                "thumbnail": online_data.get("thumbnail_url")
            }
            self.current_online_episode = online_data["ep_no"]
            self._last_online_duration = 0
        
        # Determine source
        is_online = self.current_online_show is not None
        
        if is_online:
            show_name = self.current_online_show["name"]
            ep_display = f"Episode {self.current_online_episode}"
            thumb_path = None
            cached_url = None
            large_image_url = self.current_online_show["thumbnail"]
            
            # Handle relative URLs from AllAnime
            if large_image_url and not large_image_url.startswith("http"):
                large_image_url = f"https://allanime.day/{large_image_url.lstrip('/')}"
            
            duration = self.player_widget._duration
        else:
            if not episode:
                episode = self.current_episode
            if not episode or not self.current_series:
                return
            
            display_name = episode.title if episode.title else episode.filename
            show_name = self.current_series.name
            ep_display = display_name
            thumb_path = self.current_series.thumbnail_path
            cached_url = self.current_series.rpc_image_url
            large_image_url = None
            duration = episode.duration

        if timestamp is None:
            timestamp = self.player_widget._current_time

        # Privacy/NSFW logic
        is_safe_mode = self.nsfw_toggle.isChecked()
        if is_safe_mode:
            show_name = "Secret Series"
            ep_display = "Classified Episode"
            thumb_path = None
            cached_url = None
            large_image_url = None

        rpc_url = await self.discord.update_presence(
            series=show_name,
            episode=ep_display,
            player=self.player_widget.player_type,
            thumbnail_path=thumb_path,
            cached_thumbnail_url=cached_url,
            large_image_url=large_image_url,
            duration=duration,
            start_offset=timestamp,
            is_paused=self.player_widget.is_paused
        )
        
        # Cache RPC URL for local series
        if not is_online and not is_safe_mode and rpc_url and rpc_url != self.current_series.rpc_image_url:
            logger.info(f"Caching new RPC image URL for series: {self.current_series.name}")
            self.current_series.rpc_image_url = rpc_url
            await self.db.update_series_rpc_url(self.current_series.id, rpc_url)

    @qasync.asyncSlot(float, float)
    async def on_progress_updated(self, current, total):
        # Trigger RPC update if duration was previously unknown (0) but now discovered (>0)
        if self.current_online_show and getattr(self, "_last_online_duration", 0) == 0 and total > 0:
            self._last_online_duration = total
            await self.update_discord_rpc(timestamp=current)
            
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
        if timestamp is None:
            timestamp = self.player_widget._current_time
            
        if self.current_online_show:
            # Handle Online Progress
            from ..database.models import OnlineProgress
            is_completed = False
            if self.player_widget._duration > 0:
                if timestamp / self.player_widget._duration > 0.9:
                    is_completed = True
            
            progress = OnlineProgress(
                show_id=self.current_online_show["id"],
                show_name=self.current_online_show["name"],
                episode_number=self.current_online_episode,
                timestamp=timestamp,
                completed=is_completed
            )
            await self.db.update_online_progress(progress)
            return

        if not self.current_episode:
            return
            
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

    def on_download_progress(self, filename, progress):
        # Show progress in status bar if available, or just log
        self.statusBar().showMessage(f"Downloading {filename}: {progress:.1f}%", 5000)

    def on_download_finished(self, filename, success, message, metadata):
        if success:
            self.statusBar().showMessage(f"Download complete: {filename}", 10000)
            
            # Save to database
            if self.db and metadata:
                from ..database.models import OnlineProgress
                from ..config import DOWNLOADS_PATH
                
                async def save_cache():
                    progress = OnlineProgress(
                        show_id=metadata['show_id'],
                        show_name=metadata['show_name'],
                        episode_number=int(float(metadata['ep_no'])) if str(metadata['ep_no']).replace('.','',1).isdigit() else 0,
                        thumbnail_url=metadata.get('thumbnail_url'),
                        local_path=os.path.join(DOWNLOADS_PATH, filename)
                    )
                    await self.db.update_online_progress(progress)
                    logger.info(f"Saved local cache path for {filename} to database")
                    
                    # Notify online widget to refresh if it's showing the same show
                    if hasattr(self, 'online_widget'):
                        # This is a bit simple, but better than nothing
                        pass
                
                asyncio.create_task(save_cache())
        else:
            self.statusBar().showMessage(f"Download failed: {filename} ({message})", 10000)

    def open_online_search(self):
        # Switch to Online tab
        self.tabs.setCurrentIndex(1)

    def closeEvent(self, event):
        self.player_widget.shutdown()
        
        # Async cleanup (fire and forget in sync closeEvent)
        asyncio.create_task(self.discord.clear())
        asyncio.create_task(self.discord.shutdown())
        
        app = QApplication.instance()
        if app:
            app.quit()
        event.accept()
