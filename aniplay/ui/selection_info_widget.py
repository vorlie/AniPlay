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
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from ..utils.format_utils import format_size, format_time

class SelectionInfoWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setObjectName("SelectionInfoWidget")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            #SelectionInfoWidget {
                background-color: rgba(61, 90, 254, 0.08);
                border: none;
                border-radius: 6px;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
            .title {
                font-weight: bold;
                color: #3d5afe;
            }
            .meta {
                color: #888;
                font-size: 11px;
            }
        """)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(15, 0, 15, 0)
        self.layout.setSpacing(20)
        
        self.name_label = QLabel("Select a series to see details")
        self.name_label.setProperty("class", "title")
        self.layout.addWidget(self.name_label)
        
        self.layout.addSpacing(20)
        
        self.episodes_label = QLabel("")
        self.episodes_label.setProperty("class", "meta")
        self.layout.addWidget(self.episodes_label)
        
        self.size_label = QLabel("")
        self.size_label.setProperty("class", "meta")
        self.layout.addWidget(self.size_label)
        
        self.hide() # Hidden by default

    def update_info(self, name: str, episodes_count: int, size_bytes: int):
        self.name_label.setText(name)
        self.episodes_label.setText(f"Episodes: {episodes_count}")
        self.size_label.setText(f"Total Size: {format_size(size_bytes)}")
        self.show()
