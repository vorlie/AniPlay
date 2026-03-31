# AniPlay - Personal media server and player for anime libraries.
# Copyright (C) 2026  Charlie

import os
import re
import hashlib
import shutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QPushButton, 
    QLineEdit, QLabel, QMessageBox, QInputDialog, QMenu
)
from PyQt6.QtCore import Qt, QDir
from PyQt6.QtGui import QAction, QFileSystemModel
import qasync
import aiosqlite
from ..config import DOWNLOADS_PATH
from ..utils.logger import get_logger

logger = get_logger(__name__)

class LibraryManagerWidget(QWidget):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setup_ui()
        
    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        # Header / Tools
        self.tools_layout = QHBoxLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter Series Name for Hash Generation...")
        self.name_input.setFixedHeight(40)
        
        self.gen_nyaa_btn = QPushButton("📁 Create Nyaa")
        self.gen_nyaa_btn.clicked.connect(self.generate_nyaa_hash)
        
        self.copy_nyaa_btn = QPushButton("📋 Copy Hash")
        self.copy_nyaa_btn.clicked.connect(lambda: self.copy_hash("nyaa"))
        
        self.gen_allanime_btn = QPushButton("📁 Create AllAnime")
        self.gen_allanime_btn.clicked.connect(self.generate_allanime_hash)
        
        self.copy_allanime_btn = QPushButton("📋 Copy Hash")
        self.copy_allanime_btn.clicked.connect(lambda: self.copy_hash("allanime"))
        
        self.tools_layout.addWidget(self.name_input, 1)
        self.tools_layout.addWidget(self.gen_nyaa_btn)
        self.tools_layout.addWidget(self.copy_nyaa_btn)
        self.tools_layout.addWidget(self.gen_allanime_btn)
        self.tools_layout.addWidget(self.copy_allanime_btn)
        
        self.layout.addLayout(self.tools_layout)
        
        # File System Model
        self.model = QFileSystemModel()
        self.model.setRootPath(str(DOWNLOADS_PATH))
        self.model.setReadOnly(False)
        
        # Tree View
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(str(DOWNLOADS_PATH)))
        self.tree.setColumnWidth(0, 400)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QTreeView.DragDropMode.InternalMove)
        self.tree.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        
        self.layout.addWidget(self.tree)
        
        # Bottom Actions
        self.bottom_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh_view)
        
        self.relink_btn = QPushButton("🔗 Relink Folder to DB")
        self.relink_btn.clicked.connect(self.relink_folder)
        
        self.bottom_layout.addWidget(self.refresh_btn)
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.relink_btn)
        
        self.layout.addLayout(self.bottom_layout)

    def refresh_view(self):
        self.tree.setRootIndex(self.model.index(str(DOWNLOADS_PATH)))

    def copy_hash(self, provider):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a name first.")
            return
        name_hash = hashlib.md5(name.encode('utf-8')).hexdigest()[:12]
        full_id = f"{provider}-{name_hash}"
        from PyQt6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(full_id)
        self.name_input.setPlaceholderText(f"Copied: {full_id}")

    def generate_nyaa_hash(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a series name.")
            return
            
        name_hash = hashlib.md5(name.encode('utf-8')).hexdigest()[:12]
        folder_name = f"nyaa-{name_hash}"
        self.create_folder(folder_name)

    def generate_allanime_hash(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a series name.")
            return
            
        name_hash = hashlib.md5(name.encode('utf-8')).hexdigest()[:12]
        folder_name = f"allanime-{name_hash}"
        self.create_folder(folder_name)

    def create_folder(self, folder_name):
        path = os.path.join(DOWNLOADS_PATH, folder_name)
        if os.path.exists(path):
            QMessageBox.information(self, "Exists", f"Folder {folder_name} already exists.")
            return
            
        try:
            os.makedirs(path, exist_ok=True)
            self.refresh_view()
            self.name_input.clear()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create folder: {e}")

    def show_context_menu(self, position):
        indexes = self.tree.selectedIndexes()
        if not indexes:
            return
            
        menu = QMenu()
        
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        menu.addSeparator()
        relink_action = menu.addAction("Relink to Database")
        
        action = menu.exec(self.tree.viewport().mapToGlobal(position))
        
        if action == rename_action:
            self.tree.edit(indexes[0])
        elif action == delete_action:
            self.delete_selected()
        elif action == relink_action:
            self.relink_folder()

    def delete_selected(self):
        indexes = self.tree.selectedIndexes()
        if not indexes:
            return
            
        # Filter for column 0 to avoid multiple deletions of the same file
        paths = [self.model.filePath(idx) for idx in indexes if idx.column() == 0]
        
        confirm = QMessageBox.question(
            self, "Confirm Delete", 
            f"Are you sure you want to delete {len(paths)} items?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            for p in paths:
                try:
                    if os.path.isdir(p):
                        shutil.rmtree(p)
                    else:
                        os.remove(p)
                except Exception as e:
                    logger.error(f"Failed to delete {p}: {e}")
            self.refresh_view()

    @qasync.asyncSlot()
    async def relink_folder(self):
        indexes = self.tree.selectedIndexes()
        if not indexes:
            return
            
        folder_path = self.model.filePath(indexes[0])
        if not os.path.isdir(folder_path):
            QMessageBox.warning(self, "Error", "Please select a folder to relink.")
            return
            
        folder_name = os.path.basename(folder_path)
        
        # Simple relinking: ask for target show_id, show_name and allmanga_id
        show_id, ok1 = QInputDialog.getText(self, "Relink", "Target Show ID (e.g. nyaa-hash or allanime-hash):", text=folder_name)
        if not ok1 or not show_id: return
        
        show_name, ok2 = QInputDialog.getText(self, "Relink", "Target Show Name:")
        if not ok2 or not show_name: return

        allmanga_id = None
        if show_id.startswith("allanime-"):
            allmanga_id, ok3 = QInputDialog.getText(self, "Relink", "Original AllAnime ID (optional):")
        
        try:
            if hasattr(self.db, "migrate_online_show"):
                # We use the migrate method to update all entries for this folder
                await self.db.migrate_online_show(folder_name, show_id, show_name, allmanga_id=allmanga_id)
                QMessageBox.information(self, "Success", f"Folder {folder_name} relinked to {show_name} ({show_id})")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Relink failed: {e}")
