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

import os
import qasync
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, 
    QFrame, QLineEdit, QMenu, QScrollArea, QGridLayout
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QEvent
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QColor
from ..database.models import Series
from .selection_info_widget import SelectionInfoWidget

class SeriesCard(QFrame):
    clicked = pyqtSignal(object) # Series

    def __init__(self, series: Series, parent=None):
        super().__init__(parent)
        self.series = series
        self.setFixedSize(180, 260)
        self.setObjectName("SeriesCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            #SeriesCard {
                background-color: transparent;
                border: none;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Poster Container
        self.poster_label = QLabel()
        self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster_label.setStyleSheet("background-color: #1a1a1a; border-radius: 10px;")
        
        # Title Overlay
        self.overlay = QFrame(self.poster_label)
        self.overlay_layout = QVBoxLayout(self.overlay)
        self.overlay_layout.setContentsMargins(10, 10, 10, 10)
        self.overlay_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
        
        # Position overlay at bottom
        self.overlay.setGeometry(0, 150, 180, 110) # Larger overlay area
        self.overlay.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(0,0,0,0), stop:1 rgba(0,0,0,220));
            border-bottom-left-radius: 10px;
            border-bottom-right-radius: 10px;
        """)
        
        self.name_label = QLabel(series.name)
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px; background: transparent; border: none;")
        self.overlay_layout.addWidget(self.name_label)
        
        self._set_poster(series.thumbnail_path)
        self.main_layout.addWidget(self.poster_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.series)
        super().mousePressEvent(event)

    def _set_poster(self, path):
        radius = 10
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                # Scale to card size
                scaled = pixmap.scaled(
                    180, 260, 
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # Crop to fit precisely 180x260 if needed
                if scaled.width() > 180 or scaled.height() > 260:
                    scaled = scaled.copy(
                        (scaled.width() - 180) // 2,
                        (scaled.height() - 260) // 2,
                        180, 260
                    )

                # Create rounded pixmap
                rounded = QPixmap(180, 260)
                rounded.fill(QColor(0, 0, 0, 0))
                
                painter = QPainter(rounded)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                
                path = QPainterPath()
                path.addRoundedRect(0, 0, 180, 260, radius, radius)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, scaled)
                painter.end()
                
                self.poster_label.setPixmap(rounded)
                return
        
        # Fallback for missing poster
        self.poster_label.setText("🎞️")
        self.poster_label.setStyleSheet(f"font-size: 40px; border-radius: {radius}px; background-color: #1a1a1a;")

class SeriesWidget(QWidget):
    series_selected = pyqtSignal(Series)
    series_watched_toggled = pyqtSignal(Series, bool)
    poster_change_requested = pyqtSignal(Series)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(12)
        
        self.header = QLabel("Your Library")
        self.header.setStyleSheet("font-size: 16pt; font-weight: bold; color: #fff; margin-bottom: 5px;")
        self.layout.addWidget(self.header)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search your library...")
        self.search_bar.textChanged.connect(self._filter_series)
        self.layout.addWidget(self.search_bar)
        
        # Grid Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")
        
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(5, 5, 5, 5)
        self.grid_layout.setSpacing(25)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.scroll_area.setWidget(self.grid_container)
        self.layout.addWidget(self.scroll_area)
        
        self.series_widgets = [] # Store widgets to filter
        self.series_map = {}

    def set_series(self, series_list: list[Series]):
        # Clear current grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.series_widgets = []
        self.series_map = {}
        
        # Add cards to grid
        cols = self._calculate_columns()
        for i, s in enumerate(series_list):
            card = SeriesCard(s)
            card.clicked.connect(self._on_card_clicked)
            card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            card.customContextMenuRequested.connect(lambda pos, c=card: self._show_context_menu(pos, c))
            
            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(card, row, col)
            self.series_widgets.append(card)
            self.series_map[s.id] = s

    def _calculate_columns(self):
        # Account for margins and generous spacing
        width = self.scroll_area.width()
        card_width = 195 # 180 + 15 min padding
        return max(1, width // card_width)

    def _on_card_clicked(self, series):
        self.series_selected.emit(series)

    def _filter_series(self, text):
        search_text = text.lower()
        visible_items = []
        
        for card in self.series_widgets:
            is_visible = search_text in card.series.name.lower()
            card.setVisible(is_visible)
            if is_visible:
                visible_items.append(card)
        
        # Relayout visible items
        cols = self._calculate_columns()
        for i, card in enumerate(visible_items):
            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(card, row, col)

    def _show_context_menu(self, pos, card):
        series = card.series
        if not series:
            return
            
        menu = QMenu(self)
        
        mark_all_watched = menu.addAction("Mark All as Watched")
        mark_all_unwatched = menu.addAction("Clear Progress for All")
        menu.addSeparator()
        change_poster = menu.addAction("🖼️ Change Poster Manually")
        
        action = menu.exec(card.mapToGlobal(pos))
        if action == mark_all_watched:
            self.series_watched_toggled.emit(series, True)
        elif action == mark_all_unwatched:
            self.series_watched_toggled.emit(series, False)
        elif action == change_poster:
            self.poster_change_requested.emit(series)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Update layout since columns might change
        self._filter_series(self.search_bar.text())
