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
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
    QPushButton, QListWidget, QListWidgetItem, QLabel, 
    QStackedWidget, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
import qasync

from ..utils.ani_scraper import AniScraper
from ..utils.logger import get_logger
from ..database.models import OnlineProgress

logger = get_logger(__name__)

class OnlineSearchWidget(QWidget):
    def __init__(self, player_widget=None, db_manager=None, main_window=None, download_manager=None):
        super().__init__()
        self.scraper = AniScraper()
        self.player_widget = player_widget
        self.db_manager = db_manager
        self.main_window = main_window
        self.download_manager = download_manager
        self._current_episode_progress = None
        
        self.setup_ui()
        self.apply_styles()
        
        # Initial load
        asyncio.create_task(self.load_recent())

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(15)

        # Header with Search
        self.search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for anime...")
        self.search_input.returnPressed.connect(self.run_search)
        
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.clicked.connect(self.run_search)
        
        self.player_choice = QComboBox()
        self.player_choice.addItems(["Internal Player", "External mpv"])
        self.player_choice.setToolTip("Select playback method")
        
        self.search_layout.addWidget(self.search_input, 1)
        self.search_layout.addWidget(self.search_btn)
        self.search_layout.addSpacing(10)
        self.search_layout.addWidget(self.player_choice)
        
        self.main_layout.addLayout(self.search_layout)

        # Views Stack
        self.stack = QStackedWidget()
        
        # 1. Search Results / Recent
        self.results_page = QWidget()
        self.results_layout = QVBoxLayout(self.results_page)
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.on_anime_selected)
        self.results_layout.addWidget(self.results_list)
        self.stack.addWidget(self.results_page)
        
        # 2. Episode List
        self.episodes_page = QWidget()
        self.episodes_layout = QVBoxLayout(self.episodes_page)
        
        self.episode_header_layout = QHBoxLayout()
        self.back_to_results_btn = QPushButton("← Back to Results")
        self.back_to_results_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.episode_label = QLabel("Episodes:")
        
        self.bulk_download_btn = QPushButton("📥 Bulk Download")
        self.bulk_download_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                border: none;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #388e3c;
            }
        """)
        self.bulk_download_btn.clicked.connect(self.on_bulk_download_clicked)
        
        self.episode_header_layout.addWidget(self.back_to_results_btn)
        self.episode_header_layout.addWidget(self.episode_label)
        self.episode_header_layout.addStretch()
        self.episode_header_layout.addWidget(self.bulk_download_btn)
        
        self.episodes_list = QListWidget()
        self.episodes_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.episodes_list.itemDoubleClicked.connect(self.on_episode_selected)
        
        # Add context menu for episodes
        self.episodes_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.episodes_list.customContextMenuRequested.connect(self.show_episode_context_menu)
        
        self.episodes_layout.addLayout(self.episode_header_layout)
        self.episodes_layout.addWidget(self.episodes_list)
        self.stack.addWidget(self.episodes_page)
        
        # 3. Link Selection / Quality
        self.links_page = QWidget()
        self.links_layout = QVBoxLayout(self.links_page)
        self.link_header_layout = QHBoxLayout()
        self.back_to_episodes_btn = QPushButton("← Back to Episodes")
        self.back_to_episodes_btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        
        self.resume_btn = QPushButton("▶ Resume at 0:00")
        self.resume_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d5afe;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #536dfe;
            }
        """)
        self.resume_btn.hide()
        self.resume_btn.clicked.connect(self.on_resume_clicked)
        
        self.download_btn = QPushButton("📥 Download")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #388e3c;
            }
        """)
        self.download_btn.hide()
        self.download_btn.clicked.connect(self.on_download_clicked)
        
        self.play_cached_btn = QPushButton("▶ Play Now")
        self.play_cached_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #42a5f5;
            }
        """)
        self.play_cached_btn.hide()
        self.play_cached_btn.clicked.connect(self.on_play_cached_clicked)
        
        self.link_label = QLabel("Select Quality:")
        self.link_header_layout.addWidget(self.back_to_episodes_btn)
        self.link_header_layout.addWidget(self.resume_btn)
        self.link_header_layout.addWidget(self.play_cached_btn)
        self.link_header_layout.addWidget(self.download_btn)
        self.link_header_layout.addStretch()
        self.link_header_layout.addWidget(self.link_label)
        
        self.links_list = QListWidget()
        self.links_list.itemDoubleClicked.connect(self.on_link_selected)
        
        self.links_layout.addLayout(self.link_header_layout)
        self.links_layout.addWidget(self.links_list)
        self.stack.addWidget(self.links_page)

        self.main_layout.addWidget(self.stack)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; font-style: italic;")
        self.main_layout.addWidget(self.status_label)

    def apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #e0e0e0;
                font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            }
            QLineEdit {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 10px;
                selection-background-color: #3d5afe;
            }
            QLineEdit:focus {
                border: 1px solid #3d5afe;
            }
            QPushButton {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2a2a2a;
                border: 1px solid #444;
            }
            QPushButton:pressed {
                background-color: #3d5afe;
                color: white;
            }
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 12px;
                padding: 5px;
                outline: none;
            }
            QListWidget::item {
                padding: 12px;
                border-radius: 8px;
                margin: 2px 5px;
            }
            QListWidget::item:hover {
                background-color: #2a2a2a;
            }
            QListWidget::item:selected {
                background-color: #3d5afe;
                color: white;
            }
            QComboBox {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 5px 10px;
            }
            QComboBox::drop-down {
                border: 0px;
            }
            QLabel {
                font-size: 10pt;
            }
        """)

    def show_episode_context_menu(self, pos):
        item = self.episodes_list.itemAt(pos)
        if not item: 
            return
        
        data = item.data(Qt.ItemDataRole.UserRole)
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        
        is_watched = "✅" in item.text()
        
        action = menu.addAction("Mark as Watched" if not is_watched else "Mark as Unwatched")
        action.triggered.connect(lambda: asyncio.create_task(self.toggle_watched(item)))
        
        menu.exec(self.episodes_list.mapToGlobal(pos))

    async def toggle_watched(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        show_id = data['show_id']
        ep_no = data['ep_no']
        show_name = data['show_name']
        
        is_watched = "✅" in item.text()
        
        try:
            if self.db_manager:
                ep_int = int(float(ep_no)) if str(ep_no).replace('.','',1).isdigit() else 0
                progress = OnlineProgress(
                    show_id=show_id,
                    show_name=show_name,
                    episode_number=ep_int,
                    completed=not is_watched,
                    thumbnail_url=data.get('thumbnail_url')
                )
                await self.db_manager.update_online_progress(progress)
                
                # Update UI label
                if not is_watched:
                    item.setText(f"Episode {ep_no} ✅")
                    item.setForeground(Qt.GlobalColor.gray)
                else:
                    item.setText(f"Episode {ep_no}")
                    item.setForeground(Qt.GlobalColor.white)
                
                # Refresh recent list in background
                await self.load_recent()
        except Exception as e:
            logger.error(f"Error toggling watched status: {e}")
            self.status_label.setText(f"Error updating status: {e}")

    def format_time(self, seconds):
        if seconds is None: 
            return "0:00"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    async def load_recent(self):
        if not self.db_manager:
            return
            
        try:
            recent = await self.db_manager.get_recent_online_shows()
            downloaded = await self.db_manager.get_downloaded_online_shows()
            
            if self.stack.currentIndex() == 0 and not self.search_input.text():
                self.results_list.clear() # Only clear if we are showing "Recent"
                
                if downloaded:
                    header = QListWidgetItem("--- MY DOWNLOADS 📂 ---")
                    header.setFlags(Qt.ItemFlag.NoItemFlags)
                    header.setData(Qt.ItemDataRole.UserRole, None)
                    header.setForeground(Qt.GlobalColor.gray)
                    self.results_list.addItem(header)
                    
                    for show in downloaded:
                        item = QListWidgetItem(show["show_name"])
                        show_data = {
                            "_id": show["show_id"], 
                            "name": show["show_name"],
                            "thumbnail": show.get("thumbnail_url"),
                            "is_downloaded": True
                        }
                        item.setData(Qt.ItemDataRole.UserRole, show_data)
                        self.results_list.addItem(item)

                if recent:
                    header = QListWidgetItem("--- RECENTLY WATCHED 🕒 ---")
                    header.setFlags(Qt.ItemFlag.NoItemFlags)
                    header.setData(Qt.ItemDataRole.UserRole, None)
                    header.setForeground(Qt.GlobalColor.gray)
                    self.results_list.addItem(header)
                    
                    for show in recent:
                        # Skip if already in downloaded to avoid duplicates
                        if any(d['show_id'] == show['show_id'] for d in downloaded):
                            continue
                            
                        item = QListWidgetItem(show["show_name"])
                        show_data = {
                            "_id": show["show_id"], 
                            "name": show["show_name"],
                            "thumbnail": show.get("thumbnail_url")
                        }
                        item.setData(Qt.ItemDataRole.UserRole, show_data)
                        self.results_list.addItem(item)
                
                self.status_label.setText("Loaded recent and downloaded shows.")
        except Exception as e:
            logger.error(f"Error loading recent: {e}")

    @qasync.asyncSlot()
    async def run_search(self):
        query = self.search_input.text().strip()
        if not query:
            await self.load_recent()
            return
        
        self.search_btn.setEnabled(False)
        self.status_label.setText(f"Searching for '{query}'...")
        self.results_list.clear()
        
        try:
            results = await self.scraper.search(query)
            for res in results:
                item = QListWidgetItem(res['name'])
                item.setData(Qt.ItemDataRole.UserRole, res)
                self.results_list.addItem(item)
            
            if not results:
                self.status_label.setText("No results found.")
            else:
                self.status_label.setText(f"Found {len(results)} results.")
                self.stack.setCurrentIndex(0)
        except Exception as e:
            logger.error(f"Search error: {e}")
            self.status_label.setText(f"Error: {e}")
        finally:
            self.search_btn.setEnabled(True)

    @qasync.asyncSlot(QListWidgetItem)
    async def on_anime_selected(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        show_id = data['_id']
        show_name = data['name']
        thumbnail_url = data.get('thumbnail')
        
        self.status_label.setText(f"Loading episodes for {show_name}...")
        self.episodes_list.clear()
        self.episode_label.setText(f"Episodes for {show_name}:")
        
        progress_list = []
        if self.db_manager:
            progress_list = await self.db_manager.get_online_progress_for_show(show_id)
            
        try:
            episodes = await self.scraper.get_episodes(show_id)
            watched_episodes = [p.episode_number for p in progress_list if p.completed]

            for ep in episodes:
                try:
                    ep_int = int(float(ep))
                except (ValueError, TypeError):
                    ep_int = ep
                    
                label = f"Episode {ep}"
                if ep_int in watched_episodes:
                    label += " ✅"
                
                epi_item = QListWidgetItem(label)
                if ep_int in watched_episodes:
                    epi_item.setForeground(Qt.GlobalColor.gray)
                
                epi_data = {
                    "show_id": show_id, 
                    "ep_no": ep, 
                    "show_name": show_name,
                    "thumbnail_url": thumbnail_url,
                    "url": f"https://allanime.day/anime/{show_id}/episodes/{ep}", # Fallback URL
                    "local_path": None
                }
                
                is_downloaded = False
                if self.download_manager:
                    safe_name = f"{show_name} - Ep {ep}".replace("/", "_").replace("\\", "_").replace(":", "_")
                    is_downloaded = self.download_manager.get_local_path(safe_name) is not None
                    
                    for p in progress_list:
                        if p.episode_number == ep_int and p.local_path and os.path.exists(p.local_path):
                            is_downloaded = True
                            epi_data["local_path"] = p.local_path
                            break
                            
                    if is_downloaded:
                        epi_item.setText(f"Episode {ep} 💾" + (" ✅" if ep_int in watched_episodes else ""))
                
                epi_item.setData(Qt.ItemDataRole.UserRole, epi_data)
                self.episodes_list.addItem(epi_item)
            
            self.stack.setCurrentIndex(1)
            self.status_label.setText(f"Loaded {len(episodes)} episodes.")
        except Exception as e:
            logger.error(f"Error fetching episodes: {e}")
            # Offline Fallback: Show only downloaded episodes
            cached_episodes = [p for p in progress_list if p.local_path and os.path.exists(p.local_path)]
            if cached_episodes:
                self.status_label.setText(f"Offline Mode: Showing {len(cached_episodes)} cached episodes.")
                for p in cached_episodes:
                    label = f"Episode {p.episode_number} 💾"
                    if p.completed: label += " ✅"
                    
                    item = QListWidgetItem(label)
                    item.setData(Qt.ItemDataRole.UserRole, {
                        "show_id": show_id,
                        "ep_no": str(p.episode_number),
                        "show_name": show_name,
                        "thumbnail_url": thumbnail_url,
                        "url": "", # No URL in offline mode
                        "local_path": p.local_path
                    })
                    self.episodes_list.addItem(item)
                self.stack.setCurrentIndex(1)
            else:
                self.status_label.setText(f"Failed to load episodes (Offline?): {e}")

    @qasync.asyncSlot(QListWidgetItem)
    async def on_episode_selected(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        show_id = data['show_id']
        ep_no = data['ep_no']
        show_name = data['show_name']
        
        self.status_label.setText(f"Checking for cached version of Ep {ep_no}...")
        self.links_list.clear()
        self.link_label.setText(f"Select Quality for {show_name} Ep {ep_no}:")
        
        # Priority 1: Check if already cached (Bypass everything or show RESUME)
        local_path = data.get('local_path')
        if local_path and os.path.exists(local_path):
            # Check for actual progress first
            has_progress = False
            if self.db_manager:
                try:
                    progress_list = await self.db_manager.get_online_progress_for_show(show_id)
                    ep_float = float(int(float(ep_no)) if str(ep_no).replace('.','',1).isdigit() else 0)
                    for p in progress_list:
                        if p.episode_number == ep_float and p.timestamp > 5:
                            # We have progress! Let's show the resume option
                            self._current_episode_progress = p
                            self.resume_btn.setText(f"▶ Resume at {self.format_time(p.timestamp)}")
                            self.resume_btn.show()
                            
                            self.links_list.hide()
                            self.link_label.setText(f"Episode {ep_no} is cached.")
                            self.play_cached_btn.show()
                            self.download_btn.hide()
                            self.stack.setCurrentIndex(2)
                            return
                except Exception as pe:
                    logger.error(f"Error checking cached progress: {pe}")

            # No progress or skipped, just play now
            self.status_label.setText(f"Playing Ep {ep_no} from cache...")
            
            # Setup dummy progress object
            self._current_episode_progress = OnlineProgress(
                show_id=show_id,
                show_name=show_name,
                episode_number=int(float(ep_no)) if str(ep_no).replace('.','',1).isdigit() else 0,
                timestamp=0,
                local_path=local_path,
                thumbnail_url=data.get('thumbnail_url')
            )
            
            dummy_item = QListWidgetItem()
            dummy_item.setData(Qt.ItemDataRole.UserRole, data)
            self.on_link_selected(dummy_item)
            return

        try:
            self.status_label.setText(f"Fetching links for Episode {ep_no}...")
            self.play_cached_btn.hide() # Hide for online
            self.links_list.show() # Show list for online
            links = await self.scraper.get_stream_urls(show_id, ep_no)
            for link in links:
                quality = link['quality']
                source = link['source'].split(' (')[0]
                label = f"{quality} - {source}"
                if link.get('recommended'):
                    label += " (Recommended ⭐)"
                
                link_item = QListWidgetItem(label)
                if link.get('recommended'):
                    link_item.setForeground(Qt.GlobalColor.green)
                
                link_item.setData(Qt.ItemDataRole.UserRole, {
                    **link, 
                    "show_id": show_id, 
                    "show_name": show_name, 
                    "ep_no": ep_no,
                    "thumbnail_url": data.get("thumbnail_url")
                })
                self.links_list.addItem(link_item)
            
            self.stack.setCurrentIndex(2)
            self.status_label.setText(f"Found {len(links)} links.")
            
            # Show download button if links available
            if links:
                self.download_btn.show()
            else:
                self.download_btn.hide()
            
            # Check for progress to show Resume button
            self.resume_btn.hide()
            self._current_episode_progress = None
            if self.db_manager:
                try:
                    progress_list = await self.db_manager.get_online_progress_for_show(show_id)
                    ep_float = float(ep_no)
                    for p in progress_list:
                        if p.episode_number == ep_float and p.timestamp > 5:
                             self._current_episode_progress = p
                             self.resume_btn.setText(f"▶ Resume at {self.format_time(p.timestamp)}")
                             self.resume_btn.show()
                             break
                except Exception as pe:
                    logger.error(f"Error checking episode progress: {pe}")
        except Exception as e:
            logger.error(f"Error fetching links: {e}")
            self.status_label.setText(f"Error: {e}")

    def on_resume_clicked(self):
        if not self._current_episode_progress:
            return
            
        # If we have a local path, play it directly
        if self._current_episode_progress.local_path and os.path.exists(self._current_episode_progress.local_path):
            self.status_label.setText("Resuming cached file...")
            dummy_item = QListWidgetItem()
            dummy_item.setData(Qt.ItemDataRole.UserRole, {
                "show_id": self._current_episode_progress.show_id,
                "ep_no": str(self._current_episode_progress.episode_number),
                "show_name": self._current_episode_progress.show_name,
                "thumbnail_url": self._current_episode_progress.thumbnail_url,
                "url": "",
                "local_path": self._current_episode_progress.local_path
            })
            self.on_link_selected(dummy_item, start_time=self._current_episode_progress.timestamp)
            return

        best_item = None
        for i in range(self.links_list.count()):
            item = self.links_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data.get('recommended'):
                best_item = item
                break
        
        if not best_item and self.links_list.count() > 0:
            best_item = self.links_list.item(0)
            
        if best_item:
            self.on_link_selected(best_item, start_time=self._current_episode_progress.timestamp)

    def on_download_clicked(self):
        # Use selected item if any, otherwise first recommended, otherwise first link
        best_item = self.links_list.currentItem()
        
        if not best_item:
            for i in range(self.links_list.count()):
                item = self.links_list.item(i)
                data = item.data(Qt.ItemDataRole.UserRole)
                if data and data.get('recommended'):
                    best_item = item
                    break
        
        if not best_item and self.links_list.count() > 0:
            best_item = self.links_list.item(0)
            
        if best_item and self.download_manager:
            data = best_item.data(Qt.ItemDataRole.UserRole)
            show_name = data['show_name']
            ep_no = data['ep_no']
            safe_name = f"{show_name} - Ep {ep_no}".replace("/", "_").replace("\\", "_").replace(":", "_")
            
            metadata = {
                "show_id": data.get('show_id'),
                "show_name": show_name,
                "ep_no": ep_no,
                "thumbnail_url": data.get('thumbnail_url')
            }
            
            if self.download_manager.start_download(data['url'], safe_name, referrer=data.get('referrer'), metadata=metadata):
                self.status_label.setText(f"Started download: {safe_name}")
            else:
                self.status_label.setText(f"Download already in progress for {safe_name}")

    def on_play_cached_clicked(self):
        if not self._current_episode_progress or not self._current_episode_progress.local_path:
            return
            
        # Play from start (ignoring existing progress timestamp)
        self.status_label.setText("Playing cached file from start...")
        if self.player_widget:
            self.player_widget.load_video(self._current_episode_progress.local_path, start_time=0)
            self.player_widget.info_label.setText(f"Cached: {self._current_episode_progress.show_name} - Ep {self._current_episode_progress.episode_number}")

    @qasync.asyncSlot()
    async def on_bulk_download_clicked(self):
        selected_items = self.episodes_list.selectedItems()
        if not selected_items:
            self.status_label.setText("No episodes selected for bulk download.")
            return
            
        self.status_label.setText(f"Preparing bulk download for {len(selected_items)} episodes...")
        self.bulk_download_btn.setEnabled(False)
        
        try:
            # Sort items by episode number (to queue in order)
            selected_items.sort(key=lambda x: float(x.data(Qt.ItemDataRole.UserRole).get('ep_no', 0)))
            
            queued_count = 0
            for item in selected_items:
                episode_data = item.data(Qt.ItemDataRole.UserRole)
                ep_url = episode_data['url']
                ep_no = episode_data['ep_no']
                show_name = episode_data['show_name']
                
                self.status_label.setText(f"Fetching links for Ep {ep_no} ({queued_count+1}/{len(selected_items)})...")
                links = await self.scraper.get_stream_urls(episode_data.get('show_id'), ep_no)
                
                best_link = None
                for link in links:
                    if link.get('recommended'):
                        best_link = link
                        break
                if not best_link and links:
                    best_link = links[0]
                    
                if best_link and self.download_manager:
                    safe_name = f"{show_name} - Ep {ep_no}".replace("/", "_").replace("\\", "_").replace(":", "_")
                    metadata = {
                        "show_id": episode_data.get('show_id'),
                        "show_name": show_name,
                        "ep_no": ep_no,
                        "thumbnail_url": episode_data.get('thumbnail_url')
                    }
                    if self.download_manager.start_download(
                        best_link['url'], 
                        safe_name, 
                        referrer=best_link.get('referrer'),
                        metadata=metadata
                    ):
                        queued_count += 1
            
            self.status_label.setText(f"Successfully queued {queued_count} episodes for download.")
            # Clear selection after queueing
            self.episodes_list.clearSelection()
        except Exception as e:
            logger.error(f"Bulk download error: {e}")
            self.status_label.setText(f"Bulk download failed at {queued_count} episodes: {e}")
        finally:
            self.bulk_download_btn.setEnabled(True)

    def on_link_selected(self, item, start_time=0):
        data = item.data(Qt.ItemDataRole.UserRole)
        url = data['url']
        referrer = data.get('referrer')
        subtitle = data.get('subtitle')
        show_name = data['show_name']
        ep_no = data['ep_no']
        title = f"{show_name} - Episode {ep_no}"
        
        # 1. Update DB and RPC metadata (Shared for both Cache and Stream)
        if self.db_manager:
            async def update_and_refresh():
                from ..database.models import OnlineProgress
                await self.db_manager.update_online_progress(OnlineProgress(
                    show_id=data.get('show_id'),
                    show_name=show_name,
                    episode_number=int(float(ep_no)) if str(ep_no).replace('.','',1).isdigit() else 0,
                    timestamp=start_time,
                    thumbnail_url=data.get('thumbnail_url'),
                    completed=False
                ))
                await self.load_recent()
            
            asyncio.create_task(update_and_refresh())

        if self.main_window:
            asyncio.create_task(self.main_window.update_discord_rpc(online_data={
                "show_id": data.get('show_id'),
                "show_name": show_name,
                "ep_no": ep_no,
                "thumbnail_url": data.get('thumbnail_url')
            }, timestamp=start_time))

        # 2. Check for local cache (DB preferred, then safe_name)
        local_path = None
        if self._current_episode_progress and self._current_episode_progress.local_path:
            if os.path.exists(self._current_episode_progress.local_path):
                local_path = self._current_episode_progress.local_path
        
        if not local_path and self.download_manager:
            safe_name = f"{show_name} - Ep {ep_no}".replace("/", "_").replace("\\", "_").replace(":", "_")
            local_path = self.download_manager.get_local_path(safe_name)
            
        if local_path:
            logger.info(f"Using cached file: {local_path}")
            self.status_label.setText(f"Playing {title} from cache...")
            if self.player_widget:
                # We could add a callback here if load_video failed, but usually file exists check is enough
                self.player_widget.load_video(local_path, start_time=start_time)
                self.player_widget.info_label.setText(f"Cached: {title}")
                
                # Fallback check: if it's a tiny file (corrupt download), we might want to stream instead
                if os.path.getsize(local_path) < 1024 * 1024: # < 1MB
                    logger.warning(f"Cached file too small ({os.path.getsize(local_path)} bytes), falling back to stream")
                else:
                    return

        # 3. Stream if no cache
        if not url:
            self.status_label.setText("Error: No stream link available (Offline?)")
            return

        if self.player_choice.currentText() == "Internal Player" and self.player_widget:
            self.status_label.setText(f"Playing {title} in internal player...")
            self.player_widget.load_video(url, start_time=start_time, referrer=referrer, subtitle=subtitle)
            self.player_widget.info_label.setText(f"Online: {title}")
        else:
            self.launch_mpv(url, referrer, title, subtitle, start_time=start_time)

    def launch_mpv(self, url, referrer=None, title=None, subtitle=None, start_time=0):
        logger.info(f"Launching external mpv for: {url}")
        cmd = ["mpv", url]
        if referrer: 
            cmd.append(f"--referrer={referrer}")
        if title: 
            cmd.append(f"--force-media-title={title}")
        if subtitle: 
            cmd.append(f"--sub-file={subtitle}")
        if start_time > 0: 
            cmd.append(f"--start={int(start_time)}")
        cmd.extend(["--fs", "--keep-open=yes", "--osd-level=1"])
        
        try:
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
            self.status_label.setText("Launched external mpv.")
        except Exception as e:
            logger.error(f"Error launching mpv: {e}")
            self.status_label.setText(f"Error launching mpv: {e}")
