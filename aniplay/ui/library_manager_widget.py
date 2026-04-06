# AniPlay - Personal media server and player for anime libraries.
# Copyright (C) 2026  Charlie

import os
import re
import asyncio
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

        self.import_btn = QPushButton("📥 Import Downloads")
        self.import_btn.clicked.connect(self.import_downloaded_shows)
        
        self.bottom_layout.addWidget(self.refresh_btn)
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.import_btn)
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
            from ..core.online_library_manager import OnlineLibraryManager

            # Normalize target folder path for show_id and move if needed.
            ol_manager = OnlineLibraryManager(DOWNLOADS_PATH, self.db)
            if show_id.startswith("nyaa-"):
                new_folder_name = show_id
            elif show_id.startswith("allanime-"):
                new_folder_name = show_id
            else:
                new_folder_name = ol_manager.get_allanime_folder_name(show_id)

            new_folder_path = os.path.join(DOWNLOADS_PATH, new_folder_name)
            if os.path.isdir(folder_path) and os.path.normpath(folder_path) != os.path.normpath(new_folder_path):
                if os.path.isdir(new_folder_path):
                    # Merge content into existing canonical folder
                    for f in os.listdir(folder_path):
                        src = os.path.join(folder_path, f)
                        dst = os.path.join(new_folder_path, f)
                        if not os.path.exists(dst):
                            shutil.move(src, dst)
                    try:
                        os.rmdir(folder_path)
                    except OSError:
                        pass
                else:
                    shutil.move(folder_path, new_folder_path)

            if hasattr(self.db, "migrate_online_show"):
                await self.db.migrate_online_show(folder_name, show_id, show_name, allmanga_id=allmanga_id)
                QMessageBox.information(self, "Success", f"Folder {folder_name} relinked to {show_name} ({show_id})")

            self.refresh_view()
            parent_window = getattr(self, 'main_window', None) or self.parent()
            if parent_window and hasattr(parent_window, 'online_widget'):
                asyncio.create_task(parent_window.online_widget.load_recent())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Relink failed: {e}")

    @qasync.asyncSlot()
    async def import_downloaded_shows(self):
        from ..database.models import OnlineProgress
        from ..config import VIDEO_EXTENSIONS

        if not self.db:
            QMessageBox.warning(self, "Error", "No database connection available.")
            return

        existing = await self.db.get_downloaded_online_shows()
        existing_ids = {item['show_id'] for item in existing}

        def extract_episode_number(filename: str):
            patterns = [
                r'[Ss](\d{1,2})[Ee](\d{1,3})',
                r'[Ee]pisode[\s._-]?(\d{1,3})',
                r'[Ee]p[\s._-]?(\d{1,3})',
                r'\b(\d{1,3})\b'
            ]
            for pat in patterns:
                match = re.search(pat, filename)
                if match:
                    try:
                        return int(match.group(2) if len(match.groups()) > 1 else match.group(1))
                    except Exception:
                        continue
            return 0

        def extract_show_name_from_filename(path: str):
            name = os.path.basename(path)
            patterns = [
                r'^(?P<name>.+?)\s*[-_]\s*[Ss]\d{1,2}[Ee]\d{1,3}',
                r'^(?P<name>.+?)\s*[-_]\s*[Ee]p\d{1,3}',
                r'^(?P<name>.+?)\s*[-_]\s*\d{1,3}',
            ]
            for pat in patterns:
                m = re.search(pat, name, re.IGNORECASE)
                if m and m.group('name').strip():
                    return m.group('name').strip()
            return None

        imported_shows = 0
        imported_episodes = 0

        for folder_name in os.listdir(DOWNLOADS_PATH):
            folder_path = os.path.join(DOWNLOADS_PATH, folder_name)
            if not os.path.isdir(folder_path):
                continue

            show_id = None
            show_name = None

            if re.match(r'^nyaa-[a-f0-9]{12}$', folder_name):
                show_id = folder_name
                show_name = folder_name
            elif re.match(r'^allanime-[a-f0-9]{12}$', folder_name):
                show_id = folder_name
                show_name = folder_name
            else:
                bracket_match = re.search(r'^(.*?)\s*\[(nyaa-[a-f0-9]{12})\]$', folder_name)
                if bracket_match:
                    show_name = bracket_match.group(1).strip()
                    show_id = bracket_match.group(2)
                else:
                    # Potential non-canonical folder names with known existing show_id inside?
                    # Try to detect from existing DB entries as fallback.
                    for item in existing:
                        if item['show_name'] and item['show_name'].lower() in folder_name.lower():
                            show_id = item['show_id']
                            show_name = item['show_name']
                            break

            if not show_id:
                continue

            # Determine show_name from file when folder name alone isn't enough
            candidate_files = []
            for root, _, files in os.walk(folder_path):
                for f in files:
                    if any(f.lower().endswith(ext) for ext in VIDEO_EXTENSIONS):
                        candidate_files.append(os.path.join(root, f))

            if not candidate_files:
                continue

            if not show_name or show_name in (show_id, f"{show_id}"):
                extracted_name = extract_show_name_from_filename(candidate_files[0])
                if extracted_name:
                    show_name = extracted_name

            # interactive prompt for user-provided show name when still unknown or still hash id
            if not show_name or show_name in (show_id, f"{show_id}"):
                default_name = "" if show_name in (None, show_id) else show_name
                show_name, ok = QInputDialog.getText(
                    self,
                    "Import Show Name",
                    f"Enter show name for folder '{folder_name}' (id={show_id}):",
                    text=default_name
                )
                if not ok or not show_name.strip():
                    continue
                show_name = show_name.strip()

            # Sanitized show_name for DB
            show_name = show_name.strip() if show_name else show_id

            # let existing_id pass through; we just import new episodes if available
            found_video = False
            for fpath in candidate_files:
                f = os.path.basename(fpath)
                found_video = True
                ep_num = extract_episode_number(f) or 0

                progress = OnlineProgress(
                    show_id=show_id,
                    show_name=show_name,
                    episode_number=ep_num,
                    local_path=fpath,
                    completed=False,
                    allmanga_id=show_id
                )

                await self.db.update_online_progress(progress)
                imported_episodes += 1

            if found_video:
                imported_shows += 1

        self.refresh_view()
        parent_window = getattr(self, 'main_window', None) or self.parent()
        if parent_window and hasattr(parent_window, 'online_widget'):
            asyncio.create_task(parent_window.online_widget.load_recent())

        QMessageBox.information(
            self,
            "Import Complete",
            f"Imported {imported_shows} shows and {imported_episodes} episodes."
        )

