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
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
import qasync
import asyncio
from ..utils.logger import get_logger

logger = get_logger(__name__)

class DownloadItemWidget(QFrame):
    cancel_requested = pyqtSignal(str) # filename
    remove_requested = pyqtSignal(str) # filename
    start_requested = pyqtSignal(str) # filename

    def __init__(self, filename, state):
        super().__init__()
        self.filename = filename
        self.status = state.get("status", "Queued")
        self.setup_ui()
        self.update_state(state)

    def setup_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedHeight(120)
        self.setStyleSheet("""
            DownloadItemWidget {
                background-color: #1e1e1e;
                border-radius: 10px;
            }
            DownloadItemWidget:hover {
                background-color: #252525;
            }
            QLabel#filename {
                font-weight: bold;
                font-size: 11pt;
                color: #ffffff;
            }
            QLabel#status {
                font-size: 9pt;
                color: #888;
            }
            QLabel#info {
                font-size: 9pt;
                color: #aaa;
            }
            QProgressBar {
                background-color: #121212;
                border: none;
                border-radius: 4px;
                height: 8px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3d5afe;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #2a2a2a;
                padding: 5px 12px;
            }
            QPushButton:hover {
                background-color: #353535;
            }
            QPushButton#cancel_btn {
                color: #f44336;
                background-color: rgba(244, 67, 54, 0.05);
            }
            QPushButton#cancel_btn:hover {
                background-color: rgba(244, 67, 54, 0.1);
            }
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 12, 15, 12)
        self.main_layout.setSpacing(8)

        # Top row: Filename and Status
        self.top_row = QHBoxLayout()
        self.filename_label = QLabel(self.filename)
        self.filename_label.setObjectName("filename")
        self.status_label = QLabel(self.status)
        self.status_label.setObjectName("status")
        
        self.top_row.addWidget(self.filename_label, 1)
        self.top_row.addWidget(self.status_label)
        self.main_layout.addLayout(self.top_row)

        # Middle row: Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.main_layout.addWidget(self.progress_bar)

        # Bottom row: Info and Actions
        self.bottom_row = QHBoxLayout()
        self.info_label = QLabel("")
        self.info_label.setObjectName("info")
        
        self.actions_layout = QHBoxLayout()
        self.actions_layout.setSpacing(10)
        
        self.folder_btn = QPushButton("📂 Folder")
        self.folder_btn.clicked.connect(self.open_folder)
        self.folder_btn.hide()
        
        self.cancel_btn = QPushButton("✖ Cancel")
        self.cancel_btn.setObjectName("cancel_btn")
        self.cancel_btn.clicked.connect(lambda: self.cancel_requested.emit(self.filename))
        
        self.remove_btn = QPushButton("🗑 Remove")
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.filename))
        self.remove_btn.hide()
        
        self.start_btn = QPushButton("▶ Start Now")
        self.start_btn.clicked.connect(lambda: self.start_requested.emit(self.filename))
        self.start_btn.hide()

        self.actions_layout.addWidget(self.folder_btn)
        self.actions_layout.addWidget(self.start_btn)
        self.actions_layout.addWidget(self.cancel_btn)
        self.actions_layout.addWidget(self.remove_btn)

        self.bottom_row.addWidget(self.info_label, 1)
        self.bottom_row.addLayout(self.actions_layout)
        self.main_layout.addLayout(self.bottom_row)

    def update_state(self, state):
        self.status = state.get("status", self.status)
        self.status_label.setText(self.status)
        
        progress = state.get("progress", 0.0)
        self.progress_bar.setValue(int(progress))
        
        speed = state.get("speed", "-")
        eta = state.get("eta", "-")
        elapsed = state.get("elapsed", "-")
        
        if self.status == "Downloading":
            self.info_label.setText(f"{progress:.1f}% • {speed} • ETA: {eta} • Elapsed: {elapsed}")
            self.cancel_btn.show()
            self.remove_btn.hide()
            self.folder_btn.hide()
            self.status_label.setStyleSheet("color: #2196f3; font-weight: bold;")
        elif self.status == "Queued":
            self.info_label.setText("Waiting in queue...")
            self.cancel_btn.show()
            self.start_btn.show()
            self.remove_btn.hide()
            self.folder_btn.hide()
            self.status_label.setStyleSheet("color: #ff9800;")
        elif self.status == "Finished":
            self.info_label.setText("Download complete.")
            self.cancel_btn.hide()
            self.start_btn.hide()
            self.remove_btn.show()
            self.folder_btn.show()
            self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #4caf50; }")
        elif self.status == "Failed":
            msg = state.get("message", "Unknown error")
            self.info_label.setText(f"Error: {msg}")
            self.cancel_btn.hide()
            self.start_btn.hide()
            self.remove_btn.show()
            self.folder_btn.hide()
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #f44336; }")

    def open_folder(self):
        from ..config import DOWNLOADS_PATH
        if os.path.exists(DOWNLOADS_PATH):
            os.startfile(DOWNLOADS_PATH)

class DownloadsWidget(QWidget):
    def __init__(self, download_manager):
        super().__init__()
        self.download_manager = download_manager
        self.items = {} # filename -> DownloadItemWidget
        self.setup_ui()
        
        # Connect signals
        self.download_manager.task_progress.connect(self.on_task_progress)
        self.download_manager.task_finished.connect(self.on_task_finished)
        self.download_manager.queue_updated.connect(self.refresh_all)
        
        self.refresh_all()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Header
        self.header = QFrame()
        self.header.setFixedHeight(60)
        self.header.setStyleSheet("background-color: #1a1a1a;")
        self.header_layout = QHBoxLayout(self.header)
        
        self.title_label = QLabel("📥 Downloads")
        self.title_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #fff;")
        
        self.clear_btn = QPushButton("🧹 Clear History")
        self.clear_btn.clicked.connect(self.clear_history)
        
        self.manage_btn = QPushButton("🗂️ Manage Library")
        self.manage_btn.setFixedHeight(40)
        self.manage_btn.clicked.connect(self.open_library_manager)
        
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.manage_btn)
        self.process_btn = QPushButton("▶ Process Queue")
        self.process_btn.clicked.connect(self.download_manager.process_queue)
        self.process_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d5afe;
                color: white;
            }
        """)
        
        self.header_layout.addWidget(self.process_btn)
        self.header_layout.addWidget(self.clear_btn)
        
        self.main_layout.addWidget(self.header)

        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background-color: transparent;")
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.container_layout.setContentsMargins(15, 15, 15, 15)
        self.container_layout.setSpacing(10)
        
        self.scroll.setWidget(self.container)
        self.main_layout.addWidget(self.scroll)

    def refresh_all(self):
        data = self.download_manager.get_all_tasks()
        states = data["states"]
        
        # Update or add items
        for filename, state in states.items():
            if filename in self.items:
                self.items[filename].update_state(state)
            else:
                self.add_item(filename, state)
        
        # Note to future me: History items that might not be in states yet but are in history list
        for entry in data["history"]:
            filename = entry["filename"]
            if filename not in self.items:
                state = {
                    "status": "Finished" if entry["success"] else "Failed",
                    "progress": 100.0 if entry["success"] else 0.0,
                    "message": entry.get("message", ""),
                    "metadata": entry.get("metadata", {})
                }
                self.add_item(filename, state)

    def add_item(self, filename, state):
        item = DownloadItemWidget(filename, state)
        item.cancel_requested.connect(self.cancel_download)
        item.remove_requested.connect(self.remove_item)
        item.start_requested.connect(self.start_task)
        self.items[filename] = item
        self.container_layout.addWidget(item)

    def on_task_progress(self, filename, progress, speed, eta, elapsed):
        if filename in self.items:
            state = self.download_manager.task_states.get(filename, {})
            self.items[filename].update_state(state)
        else:
            # Should not usually happen if refresh_all is called on queue_updated
            self.refresh_all()

    def on_task_finished(self, filename, success, message, metadata):
        if filename in self.items:
            # Small delay or direct update
            data = self.download_manager.get_all_tasks()
            state = data["states"].get(filename, {})
            self.items[filename].update_state(state)
        else:
            self.refresh_all()

    def cancel_download(self, filename):
        if self.download_manager.cancel_download(filename):
            # If it's cancelled, we might want to keep it in failed/history or just remove it
            # For now, DownloadManager._on_task_finished will handle it
            pass

    def remove_item(self, filename):
        if filename in self.items:
            widget = self.items.pop(filename)
            self.container_layout.removeWidget(widget)
            widget.deleteLater()

    def start_task(self, filename):
        if self.download_manager.force_start_task(filename):
            pass
            
            # If it was in history, it will come back on refresh unless we clear manager's state
            # but usually manual remove means just hide it or tell manager to forget it
            # For now, just hide from UI.

    def clear_history(self):
        self.download_manager.clear_history()
        # Remove all finished/failed items from UI
        to_remove = []
        for filename, item in self.items.items():
            if item.status in ["Finished", "Failed"]:
                to_remove.append(filename)
        
        for filename in to_remove:
            self.remove_item(filename)

    def open_library_manager(self):
        # Switch to Library Manager tab in main window
        parent = self.parent()
        while parent and not hasattr(parent, 'tabs'):
            parent = parent.parent()
            
        if parent:
            # Assuming Library Manager is the 4th tab (index 3)
            # Find the index dynamically if possible
            for i in range(parent.tabs.count()):
                if "Library Manager" in parent.tabs.tabText(i):
                    parent.tabs.setCurrentIndex(i)
                    break
