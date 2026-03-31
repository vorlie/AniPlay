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
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea, QFrame, QLineEdit,
    QTextEdit, QComboBox, QDialog, QFormLayout,
    QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from ..database.models import PlannerEntry
import qasync
import logging

logger = logging.getLogger(__name__)

class PlannerEntryWidget(QFrame):
    edit_requested = pyqtSignal(object) # PlannerEntry
    delete_requested = pyqtSignal(int) # entry_id
    search_requested = pyqtSignal(str, str) # show_id, show_name

    def __init__(self, entry: PlannerEntry):
        super().__init__()
        self.entry = entry
        self.setup_ui()

    def setup_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            PlannerEntryWidget {
                background-color: #1e1e1e;
                border-radius: 10px;
            }
            PlannerEntryWidget:hover {
                background-color: #252525;
            }
            QLabel#name {
                font-weight: bold;
                font-size: 12pt;
                color: #ffffff;
            }
            QLabel#status {
                font-size: 9pt;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QLabel#id_label {
                font-family: 'Consolas', 'Courier New';
                font-size: 9pt;
                color: #777;
                background-color: #121212;
                padding: 2px 6px;
                border-radius: 4px;
            }
            QLabel#notes {
                font-size: 10pt;
                color: #aaa;
                font-style: italic;
            }
            QPushButton {
                background-color: #2a2a2a;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #353535;
            }
            QPushButton#search_btn {
                background-color: #1a237e;
                color: #c5cae9;
            }
            QPushButton#search_btn:hover {
                background-color: #283593;
            }
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 12, 15, 12)
        self.main_layout.setSpacing(10)

        # Header Row: Name and Status
        self.header_layout = QHBoxLayout()
        self.name_label = QLabel(self.entry.show_name)
        self.name_label.setObjectName("name")
        self.name_label.setWordWrap(True)
        
        self.status_label = QLabel(self.entry.status)
        self.status_label.setObjectName("status")
        self._update_status_style()
        
        self.header_layout.addWidget(self.name_label, 1)
        self.header_layout.addWidget(self.status_label)
        self.main_layout.addLayout(self.header_layout)

        # Middle Row: ID and Metadata
        self.meta_layout = QHBoxLayout()
        if self.entry.show_id:
            self.id_label = QLabel(f"ID: {self.entry.show_id}")
            self.id_label.setObjectName("id_label")
            self.meta_layout.addWidget(self.id_label)
            
            self.search_btn = QPushButton("🔍 Find Online")
            self.search_btn.setObjectName("search_btn")
            self.search_btn.clicked.connect(lambda: self.search_requested.emit(self.entry.show_id, self.entry.show_name))
            self.meta_layout.addWidget(self.search_btn)
        
        self.meta_layout.addStretch()
        self.main_layout.addLayout(self.meta_layout)

        # Notes Row
        if self.entry.notes:
            self.notes_label = QLabel(f"“{self.entry.notes}”")
            self.notes_label.setObjectName("notes")
            self.notes_label.setWordWrap(True)
            self.main_layout.addWidget(self.notes_label)

        # Actions Row
        self.actions_layout = QHBoxLayout()
        self.actions_layout.setContentsMargins(0, 5, 0, 0)
        
        added_on = self.entry.date_added.strftime("%Y-%m-%d") if self.entry.date_added else "Unknown"
        self.date_label = QLabel(f"Added: {added_on}")
        self.date_label.setStyleSheet("color: #555; font-size: 8pt;")
        self.actions_layout.addWidget(self.date_label)
        
        self.actions_layout.addStretch()
        
        self.edit_btn = QPushButton("📝 Edit")
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.entry))
        
        self.delete_btn = QPushButton("🗑 Remove")
        self.delete_btn.setStyleSheet("color: #f44336; background-color: rgba(244, 67, 54, 0.05);")
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.entry.id))
        
        self.actions_layout.addWidget(self.edit_btn)
        self.actions_layout.addWidget(self.delete_btn)
        self.main_layout.addLayout(self.actions_layout)

    def _update_status_style(self):
        status = self.entry.status
        colors = {
            "Plan to Watch": ("#424242", "#ffffff"),
            "Watching": ("#1565c0", "#ffffff"),
            "Finished": ("#2e7d32", "#ffffff"),
            "Dropped": ("#c62828", "#ffffff"),
            "On Hold": ("#ef6c00", "#ffffff")
        }
        bg, fg = colors.get(status, ("#333", "#fff"))
        self.status_label.setStyleSheet(f"background-color: {bg}; color: {fg}; font-weight: bold;")

class PlannerEntryDialog(QDialog):
    def __init__(self, parent=None, entry=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle("Plan New Show" if not entry else f"Edit {entry.show_name}")
        self.setMinimumWidth(450)
        self.setup_ui()

    def setup_ui(self):
        self.layout = QFormLayout(self)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(20, 20, 20, 20)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Frieren: Beyond Journey's End")
        self.name_input.setFixedHeight(35)
        if self.entry: self.name_input.setText(self.entry.show_name)
        
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("Optional (the part after /anime/ in the URL)")
        self.id_input.setFixedHeight(35)
        if self.entry: self.id_input.setText(self.entry.show_id or "")
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Plan to Watch", "Watching", "Finished", "Dropped", "On Hold"])
        self.status_combo.setFixedHeight(35)
        if self.entry: self.status_combo.setCurrentText(self.entry.status)
        
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Any reminders or why you want to watch this...")
        self.notes_input.setMaximumHeight(100)
        self.notes_input.setStyleSheet("padding: 8px;")
        if self.entry: self.notes_input.setText(self.entry.notes)

        self.layout.addRow("Series Name:", self.name_input)
        self.layout.addRow("AllAnime ID:", self.id_input)
        self.layout.addRow("Status:", self.status_combo)
        self.layout.addRow("Planner Notes:", self.notes_input)

        self.btns = QHBoxLayout()
        self.save_btn = QPushButton("Save Entry")
        self.save_btn.setFixedHeight(40)
        self.save_btn.setStyleSheet("background-color: #3d5afe; color: white; font-weight: bold;")
        self.save_btn.clicked.connect(self.accept)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(40)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.btns.addStretch()
        self.btns.addWidget(self.cancel_btn)
        self.btns.addWidget(self.save_btn)
        self.layout.addRow(self.btns)

    def get_data(self):
        return {
            "show_name": self.name_input.text().strip(),
            "show_id": self.id_input.text().strip() if self.id_input.text().strip() else None,
            "status": self.status_combo.currentText(),
            "notes": self.notes_input.toPlainText().strip()
        }

class PlannerWidget(QWidget):
    search_requested = pyqtSignal(str, str) # Forward ID + Name to MainWindow

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.setup_ui()
        self.load_entries()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Header
        self.header = QFrame()
        self.header.setFixedHeight(70)
        self.header.setStyleSheet("background-color: #1a1a1a;")
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(20, 0, 20, 0)
        
        self.title_label = QLabel("📋 Watch Planner")
        self.title_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #fff;")
        
        self.add_btn = QPushButton("+ Plan New Show")
        self.add_btn.setMinimumWidth(150)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d5afe;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #536dfe;
            }
        """)
        self.add_btn.clicked.connect(self.on_add_clicked)
        
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.add_btn)
        self.main_layout.addWidget(self.header)

        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background-color: transparent;")
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.container_layout.setContentsMargins(20, 20, 20, 20)
        self.container_layout.setSpacing(12)
        
        self.scroll.setWidget(self.container)
        self.main_layout.addWidget(self.scroll)

    @qasync.asyncSlot()
    async def load_entries(self):
        # Clear current
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        try:
            entries = await self.db.get_all_planner_entries()
            for entry in entries:
                widget = PlannerEntryWidget(entry)
                widget.edit_requested.connect(self.on_edit_clicked)
                widget.delete_requested.connect(self.on_delete_clicked)
                widget.search_requested.connect(self.search_requested.emit)
                self.container_layout.addWidget(widget)
            
            if not entries:
                self.empty_label = QLabel("Your planner is empty.\nAdd shows you want to remember!")
                self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.empty_label.setStyleSheet("color: #555; font-size: 12pt; margin-top: 100px; font-style: italic;")
                self.container_layout.addWidget(self.empty_label)
        except Exception as e:
            logger.error(f"Failed to load planner entries: {e}")

    @qasync.asyncSlot()
    async def on_add_clicked(self):
        dialog = PlannerEntryDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if not data["show_name"]:
                QMessageBox.warning(self, "Missing Name", "Please enter a show name.")
                return
            
            entry = PlannerEntry(**data)
            await self.db.add_planner_entry(entry)
            await self.load_entries()

    @qasync.asyncSlot(object)
    async def on_edit_clicked(self, entry):
        dialog = PlannerEntryDialog(self, entry)
        if dialog.exec():
            data = dialog.get_data()
            if not data["show_name"]:
                return

            entry.show_name = data["show_name"]
            entry.show_id = data["show_id"]
            entry.status = data["status"]
            entry.notes = data["notes"]
            
            await self.db.update_planner_entry(entry)
            await self.load_entries()

    @qasync.asyncSlot(int)
    async def on_delete_clicked(self, entry_id):
        confirm = QMessageBox.question(
            self, "Remove Entry", 
            "Are you sure you want to remove this show from your planner?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            await self.db.remove_planner_entry(entry_id)
            await self.load_entries()
