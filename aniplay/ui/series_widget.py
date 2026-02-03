import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel, QHBoxLayout, QFrame, QLineEdit, QMenu
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPainterPath, QColor, QBrush
from ..database.models import Series

class SeriesCard(QFrame):
    def __init__(self, series: Series, parent=None):
        super().__init__(parent)
        self.series = series
        self.setFixedSize(180, 260) # Portrait aspect ratio for posters
        self.setObjectName("SeriesCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            #SeriesCard {
                border-radius: 12px;
                background-color: rgba(255, 255, 255, 0.02);
            }
            #SeriesCard:hover {
                border: 2px solid #3d5afe;
                background-color: rgba(61, 90, 254, 0.1);
            }
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Poster Container (takes most of the card)
        self.poster_label = QLabel()
        self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster_label.setStyleSheet("border-radius: 12px;")
        
        # Title Overlay
        self.overlay = QFrame(self.poster_label)
        self.overlay_layout = QVBoxLayout(self.overlay)
        self.overlay_layout.setContentsMargins(10, 10, 10, 10)
        self.overlay_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
        
        # Position overlay at bottom
        self.overlay.setGeometry(0, 150, 180, 110) # Larger overlay area
        self.overlay.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(0,0,0,0), stop:1 rgba(0,0,0,220));
            border-bottom-left-radius: 12px;
            border-bottom-right-radius: 12px;
        """)
        
        self.name_label = QLabel(series.name)
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px; background: transparent; border: none;")
        self.overlay_layout.addWidget(self.name_label)
        
        self._set_rounded_poster(series.thumbnail_path)
        self.main_layout.addWidget(self.poster_label)

    def _set_rounded_poster(self, path):
        radius = 12
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                # Scale first
                scaled = pixmap.scaled(
                    180, 260, 
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # Create rounded version
                rounded = QPixmap(scaled.size())
                rounded.fill(QColor(0, 0, 0, 0))
                
                painter = QPainter(rounded)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                
                path = QPainterPath()
                path.addRoundedRect(0, 0, scaled.width(), scaled.height(), radius, radius)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, scaled)
                painter.end()
                
                self.poster_label.setPixmap(rounded)
                return
        
        # Fallback for missing poster
        self.poster_label.setText("🎞️")
        self.poster_label.setStyleSheet(f"font-size: 40px; border-radius: {radius}px; background-color: #2a2a2a;")

class SeriesWidget(QWidget):
    series_selected = pyqtSignal(Series)
    series_watched_toggled = pyqtSignal(Series, bool)
    poster_change_requested = pyqtSignal(Series)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.header = QLabel("Your Library")
        self.header.setStyleSheet("""
            font-size: 24px; 
            font-weight: bold; 
            margin: 10px 0px 15px 0px;
            color: rgba(255, 255, 255, 0.9);
        """)
        self.layout.addWidget(self.header)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search series...")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                border-radius: 10px;
                padding: 12px 18px;
                font-size: 14px;
                margin-bottom: 15px;
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            QLineEdit:focus {
                border: 1px solid #3d5afe;
                background-color: rgba(255, 255, 255, 0.08);
            }
        """)
        self.search_bar.textChanged.connect(self._filter_series)
        self.layout.addWidget(self.search_bar)
        
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setSpacing(18)
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
        menu.setStyleSheet("")
        
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
