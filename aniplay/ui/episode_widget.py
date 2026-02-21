from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel, QHBoxLayout, QProgressBar, QFrame, QPushButton, QMenu, QTabWidget
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from ..database.models import Episode, WatchProgress
from ..utils.format_utils import format_size, format_time

class EpisodeItem(QFrame):
    play_clicked = pyqtSignal(Episode)

    def __init__(self, episode: Episode, progress: WatchProgress = None, parent=None):
        super().__init__(parent)
        self.episode = episode
        self.setObjectName("EpisodeItem")
        
        is_completed = progress and progress.completed
        
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            #EpisodeItem {{
                background-color: rgba(255, 255, 255, 0.02);
                border-radius: 10px;
                border: 1px solid {"#00c853" if is_completed else "rgba(255, 255, 255, 0.05)"};
            }}
            #EpisodeItem:hover {{
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid #00c853;
            }}
        """)
        
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(20, 15, 20, 15)
        self.main_layout.setSpacing(20)
        
        # Info Container (Title + Progress)
        self.info_container = QWidget()
        self.info_container.setStyleSheet("background: transparent;")
        self.info_layout = QVBoxLayout(self.info_container)
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout.setSpacing(8)
        
        season_str = f"S{episode.season_number:02d}" if episode.season_number is not None else ""
        ep_str = f"E{episode.episode_number:02d}" if episode.episode_number is not None else ""
        
        display_name = episode.title if episode.title else episode.filename
        title = f"{season_str}{ep_str} - {display_name}".strip(" - ")
        
        self.title_label = QLabel(title)
        self.title_label.setWordWrap(False)
        self.title_label.setStyleSheet(f"""
            font-weight: bold; 
            font-size: 11pt;
            background: transparent;
            {'color: #00c853;' if is_completed else ''}
        """)
        # Set font explicitly to avoid -1 point size warning during metric calculation
        font = self.title_label.font()
        font.setPointSize(11)
        font.setBold(True)
        self.title_label.setFont(font)

        # Use Qt eliding to truncate long text with ellipsis
        from PyQt6.QtGui import QFontMetrics
        font_metrics = QFontMetrics(font)
        # Allow reasonable width but prevent excessive text
        max_width = 600  # Will be constrained by container anyway
        elided_text = font_metrics.elidedText(title, Qt.TextElideMode.ElideRight, max_width)
        if elided_text != title:
            self.title_label.setText(elided_text)
            self.title_label.setToolTip(title)  # Show full text on hover
        self.info_layout.addWidget(self.title_label)

        # Meta Layout (Duration)
        self.meta_label = QLabel()
        if episode.duration > 0:
            duration_str = self._format_time(episode.duration)
            size_str = format_size(episode.size_bytes)
            self.meta_label.setText(f"{duration_str} • {size_str}" if episode.size_bytes > 0 else duration_str)
            self.meta_label.setStyleSheet("""
                font-size: 9pt; 
                color: rgba(255, 255, 255, 0.6); 
                background: transparent;
                margin-top: 2px;
            """)
            self.info_layout.addWidget(self.meta_label)
        elif episode.size_bytes > 0:
            self.meta_label.setText(format_size(episode.size_bytes))
            self.meta_label.setStyleSheet("""
                font-size: 9pt; 
                color: rgba(255, 255, 255, 0.6); 
                background: transparent;
                margin-top: 2px;
            """)
            self.info_layout.addWidget(self.meta_label)
        
        if progress and episode.duration and episode.duration > 0:
            percentage = int((progress.timestamp / episode.duration) * 100)
            self.progress_bar = QProgressBar()
            self.progress_bar.setValue(percentage)
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setMaximumHeight(6)
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: none;
                    border-radius: 3px;
                    background-color: rgba(0, 0, 0, 0.3);
                }
                QProgressBar::chunk {
                    border-radius: 3px;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #00c853, stop:1 #00e676);
                }
            """)
            self.info_layout.addWidget(self.progress_bar)
        
        self.main_layout.addWidget(self.info_container, 1)

        # Status Icon/Checkmark
        if is_completed:
            self.check_label = QLabel("✅")
            self.check_label.setStyleSheet("font-size: 20px; background: transparent;")
            self.main_layout.addWidget(self.check_label)

        # Play Button
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setFixedSize(90, 40)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #00c853;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background-color: #00e676;
            }
            QPushButton:pressed {
                background-color: #00a040;
            }
        """)
        self.play_btn.clicked.connect(lambda: self.play_clicked.emit(self.episode))
        self.main_layout.addWidget(self.play_btn)

    def _format_time(self, seconds: float) -> str:
        return format_time(seconds)

class EpisodeWidget(QWidget):
    episode_selected = pyqtSignal(Episode)
    episode_watched_toggled = pyqtSignal(Episode, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.header = QLabel("Episodes")
        self.header.setStyleSheet("""
            font-size: 24px; 
            font-weight: bold; 
            margin: 15px 0px 10px 0px;
            color: rgba(255, 255, 255, 0.9);
        """)
        self.layout.addWidget(self.header)
        
        # Container for the current list view or tab widget
        self.container_layout = QVBoxLayout()
        self.layout.addLayout(self.container_layout)
        
        self.episode_map = {} # ID -> Episode object
        self.current_lists = [] # To keep track of all list widgets used

    def _create_list_widget(self):
        lw = QListWidget()
        lw.setSpacing(12)
        lw.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        lw.customContextMenuRequested.connect(self._show_context_menu)
        lw.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
            }
            QListWidget::item {
                border-radius: 10px;
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
            self.tabs.setStyleSheet("")
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
            item.setSizeHint(QSize(0, 90))
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
        menu.setStyleSheet("")
        
        mark_watched = menu.addAction("Mark as Watched")
        mark_unwatched = menu.addAction("Mark as Unwatched")
        
        action = menu.exec(sender.mapToGlobal(pos))
        if action == mark_watched:
            self.episode_watched_toggled.emit(episode, True)
        elif action == mark_unwatched:
            self.episode_watched_toggled.emit(episode, False)
