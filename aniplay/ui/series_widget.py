import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel, QHBoxLayout, QFrame, QLineEdit, QMenu
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QPixmap, QImage
from ..database.models import Series

class SeriesCard(QFrame):
    def __init__(self, series: Series, parent=None):
        super().__init__(parent)
        self.series = series
        self.setFixedSize(180, 260) # Portrait aspect ratio for posters
        self.setObjectName("SeriesCard")
        self.setStyleSheet("""
            #SeriesCard {
                background-color: #2d2d2d;
                border-radius: 12px;
                border: 1px solid #3d3d3d;
            }
            #SeriesCard:hover {
                background-color: #3d3d3d;
                border: 1px solid #3d5afe;
            }
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Poster Container (takes most of the card)
        self.poster_label = QLabel()
        self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster_label.setStyleSheet("border-radius: 12px; background-color: #1a1a1a;")
        
        if series.thumbnail_path and os.path.exists(series.thumbnail_path):
            pixmap = QPixmap(series.thumbnail_path)
            if not pixmap.isNull():
                self.poster_label.setPixmap(pixmap.scaled(
                    180, 260, 
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
                    Qt.TransformationMode.SmoothTransformation
                ))
            else:
                self.poster_label.setText("🎞️")
        else:
            self.poster_label.setText("🎞️")
            self.poster_label.setStyleSheet("font-size: 40px; color: #444;")

        # Title Overlay
        self.overlay = QFrame(self.poster_label)
        self.overlay.setGeometry(0, 200, 180, 60)
        self.overlay.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(0,0,0,0), stop:1 rgba(0,0,0,200));
            border-bottom-left-radius: 12px;
            border-bottom-right-radius: 12px;
        """)
        
        self.name_label = QLabel(series.name, self.overlay)
        self.name_label.setGeometry(10, 10, 160, 40)
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        self.name_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px; background: transparent; border: none;")
        
        self.main_layout.addWidget(self.poster_label)

class SeriesWidget(QWidget):
    series_selected = pyqtSignal(Series)
    series_watched_toggled = pyqtSignal(Series, bool)
    poster_change_requested = pyqtSignal(Series)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.header = QLabel("Your Library")
        self.header.setStyleSheet("font-size: 22px; font-weight: bold; color: #fff; margin-top: 10px;")
        self.layout.addWidget(self.header)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search series...")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                padding: 10px 15px;
                color: #fff;
                font-size: 14px;
                margin-bottom: 10px;
            }
            QLineEdit:focus {
                border: 1px solid #3d5afe;
            }
        """)
        self.search_bar.textChanged.connect(self._filter_series)
        self.layout.addWidget(self.search_bar)
        
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setSpacing(15)
        self.list_widget.setMovement(QListWidget.Movement.Static)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.setStyleSheet("""
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
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.layout.addWidget(self.list_widget)
        
        self.series_map = {} # id -> Series object

    def set_series(self, series_list: list[Series]):
        self.list_widget.clear()
        self.series_map = {}
        for s in series_list:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            item.setSizeHint(QSize(180, 260))
            self.list_widget.addItem(item)
            
            card = SeriesCard(s)
            self.list_widget.setItemWidget(item, card)
            self.series_map[s.id] = s

    def _on_item_clicked(self, item):
        series_id = item.data(Qt.ItemDataRole.UserRole)
        if series_id in self.series_map:
            self.series_selected.emit(self.series_map[series_id])

    def _filter_series(self, text):
        search_text = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            series_id = item.data(Qt.ItemDataRole.UserRole)
            series = self.series_map.get(series_id)
            if series:
                item.setHidden(search_text not in series.name.lower())

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
            
        series_id = item.data(Qt.ItemDataRole.UserRole)
        series = self.series_map.get(series_id)
        if not series:
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
        
        mark_all_watched = menu.addAction("Mark All as Watched")
        mark_all_unwatched = menu.addAction("Clear Progress for All")
        menu.addSeparator()
        change_poster = menu.addAction("🖼️ Change Poster Manually")
        
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == mark_all_watched:
            self.series_watched_toggled.emit(series, True)
        elif action == mark_all_unwatched:
            self.series_watched_toggled.emit(series, False)
        elif action == change_poster:
            self.poster_change_requested.emit(series)
