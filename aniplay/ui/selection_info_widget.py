import os
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from ..utils.format_utils import format_size, format_time

class SelectionInfoWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setObjectName("SelectionInfoWidget")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            #SelectionInfoWidget {
                background-color: rgba(61, 90, 254, 0.1);
                border: 1px solid rgba(61, 90, 254, 0.2);
                border-radius: 10px;
                margin-bottom: 15px;
            }
            QLabel {
                color: rgba(255, 255, 255, 0.9);
                font-size: 14px;
            }
            .title {
                font-weight: bold;
                color: #3d5afe;
            }
            .meta {
                color: rgba(255, 255, 255, 0.6);
                font-size: 12px;
            }
        """)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(15, 0, 15, 0)
        self.layout.setSpacing(20)
        
        self.name_label = QLabel("Select a series to see details")
        self.name_label.setProperty("class", "title")
        self.layout.addWidget(self.name_label)
        
        self.layout.addStretch()
        
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
