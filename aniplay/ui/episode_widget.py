from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel, QHBoxLayout, QProgressBar, QFrame, QPushButton, QMenu, QTabWidget
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from ..database.models import Episode, WatchProgress

class EpisodeItem(QFrame):
    play_clicked = pyqtSignal(Episode)

    def __init__(self, episode: Episode, progress: WatchProgress = None, parent=None):
        super().__init__(parent)
        self.episode = episode
        self.setObjectName("EpisodeItem")
        
        is_completed = progress and progress.completed
        
        self.setStyleSheet(f"""
            #EpisodeItem {{
                background-color: #2d2d2d;
                border-radius: 8px;
                border: 1px solid {"#00c853" if is_completed else "#3d3d3d"};
            }}
            #EpisodeItem:hover {{
                background-color: #333333;
                border: 1px solid #00c853;
            }}
            QLabel {{
                color: #e0e0e0;
                background: transparent;
            }}
            QProgressBar {{
                border: none;
                background: #1a1a1a;
                height: 4px;
                border-radius: 2px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: #00c853;
                border-radius: 2px;
            }}
        """)
        
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(15, 10, 15, 10)
        self.main_layout.setSpacing(15)
        
        # Info Container (Title + Progress)
        self.info_container = QWidget()
        self.info_layout = QVBoxLayout(self.info_container)
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout.setSpacing(5)
        
        season_str = f"S{episode.season_number:02d}" if episode.season_number is not None else ""
        ep_str = f"E{episode.episode_number:02d}" if episode.episode_number is not None else ""
        title = f"{season_str}{ep_str} - {episode.filename}".strip(" - ")
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"font-weight: bold; {'color: #00c853;' if is_completed else ''}")
        self.info_layout.addWidget(self.title_label)

        # Meta Layout (Duration)
        self.meta_label = QLabel()
        if episode.duration > 0:
            duration_str = self._format_time(episode.duration)
            self.meta_label.setText(duration_str)
            self.meta_label.setStyleSheet("color: #888; font-size: 11px;")
            self.info_layout.addWidget(self.meta_label)
        
        if progress and episode.duration and episode.duration > 0:
            percentage = int((progress.timestamp / episode.duration) * 100)
            self.progress_bar = QProgressBar()
            self.progress_bar.setValue(percentage)
            self.progress_bar.setTextVisible(False)
            self.info_layout.addWidget(self.progress_bar)
        
        self.main_layout.addWidget(self.info_container, 1)

    def _format_time(self, seconds: float) -> str:
        s = int(seconds)
        hours = s // 3600
        minutes = (s % 3600) // 60
        seconds = s % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

        # Status Icon/Checkmark
        if is_completed:
            self.check_label = QLabel("✅")
            self.main_layout.addWidget(self.check_label)

        # Play Button
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setFixedSize(80, 35)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #00c853;
                color: white;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00e676;
            }
        """)
        self.play_btn.clicked.connect(lambda: self.play_clicked.emit(self.episode))
        self.main_layout.addWidget(self.play_btn)

class EpisodeWidget(QWidget):
    episode_selected = pyqtSignal(Episode)
    episode_watched_toggled = pyqtSignal(Episode, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.header = QLabel("Episodes")
        self.header.setStyleSheet("font-size: 22px; font-weight: bold; color: #fff; margin: 10px 0;")
        self.layout.addWidget(self.header)
        
        # Container for the current list view or tab widget
        self.container_layout = QVBoxLayout()
        self.layout.addLayout(self.container_layout)
        
        self.episode_map = {} # ID -> Episode object
        self.current_lists = [] # To keep track of all list widgets used

    def _create_list_widget(self):
        lw = QListWidget()
        lw.setSpacing(8)
        lw.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        lw.customContextMenuRequested.connect(self._show_context_menu)
        lw.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
            }
            QListWidget::item {
                border-radius: 8px;
            }
            QListWidget::item:selected {
                background-color: transparent;
            }
        """)
        lw.itemDoubleClicked.connect(self._on_item_clicked)
        return lw

    def set_episodes(self, episodes: list[Episode], progress_map: dict[int, WatchProgress] = None):
        # Clear container
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.episode_map = {}
        self.current_lists = []
        progress_map = progress_map or {}
        
        # Group episodes by folder_name
        groups = {}
        for ep in episodes:
            folder = ep.folder_name or "Main"
            if folder not in groups:
                groups[folder] = []
            groups[folder].append(ep)
            self.episode_map[ep.id] = ep

        if len(groups) <= 1:
            # Simple list view
            lw = self._create_list_widget()
            self.container_layout.addWidget(lw)
            self.current_lists.append(lw)
            self._fill_list(lw, episodes, progress_map)
        else:
            # Tabbed view
            self.tabs = QTabWidget()
            self.tabs.setStyleSheet("""
                QTabWidget::pane {
                    border: none;
                    background: transparent;
                }
                QTabBar::tab {
                    background: #2d2d2d;
                    color: #888;
                    padding: 8px 20px;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    margin-right: 4px;
                }
                QTabBar::tab:selected {
                    background: #3d5afe;
                    color: white;
                }
                QTabBar::tab:hover:!selected {
                    background: #333;
                }
            """)
            self.container_layout.addWidget(self.tabs)
            
            # Sort groups (Main first, then S01, S02, etc, then others)
            sorted_folders = sorted(groups.keys(), key=lambda x: (x != "Main", x.lower()))
            
            for folder in sorted_folders:
                lw = self._create_list_widget()
                self.tabs.addTab(lw, folder)
                self.current_lists.append(lw)
                self._fill_list(lw, groups[folder], progress_map)

    def _fill_list(self, lw, episodes, progress_map):
        for ep in episodes:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, ep.id)
            item.setSizeHint(QSize(0, 70))
            lw.addItem(item)
            
            widget = EpisodeItem(ep, progress_map.get(ep.id))
            widget.play_clicked.connect(self.episode_selected.emit)
            lw.setItemWidget(item, widget)

    def _on_item_clicked(self, item):
        ep_id = item.data(Qt.ItemDataRole.UserRole)
        if ep_id in self.episode_map:
            self.episode_selected.emit(self.episode_map[ep_id])

    def _show_context_menu(self, pos):
        # Find which list widget triggered the menu
        sender = self.sender()
        if not isinstance(sender, QListWidget):
            return
            
        item = sender.itemAt(pos)
        if not item:
            return
            
        ep_id = item.data(Qt.ItemDataRole.UserRole)
        episode = self.episode_map.get(ep_id)
        if not episode:
            return
            
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #3d3d3d;
            }
            QMenu::item:selected {
                background-color: #3d5afe;
            }
        """)
        
        mark_watched = menu.addAction("Mark as Watched")
        mark_unwatched = menu.addAction("Mark as Unwatched")
        
        action = menu.exec(sender.mapToGlobal(pos))
        if action == mark_watched:
            self.episode_watched_toggled.emit(episode, True)
        elif action == mark_unwatched:
            self.episode_watched_toggled.emit(episode, False)
