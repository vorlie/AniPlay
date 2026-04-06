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

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QTableView, QPushButton, QHeaderView, QAbstractItemView,
                             QMessageBox, QLineEdit, QLabel, QWidget, QListWidget,
                             QStackedWidget, QToolBar, QStatusBar, QFrame, QCheckBox, QSizePolicy)
from PyQt6.QtCore import Qt, QAbstractTableModel, pyqtSignal, QModelIndex, QTimer, QSortFilterProxyModel, QRegularExpression
from PyQt6.QtGui import QAction, QIcon, QColor
import qasync
import asyncio
import json
from ..database.db import DatabaseManager
from ..database.models import Series, Episode, WatchProgress, MediaTrack, OnlineProgress, DownloadTaskState, PlannerEntry
from ..utils.title_extractor import TitleExtractor

class GenericTableModel(QAbstractTableModel):
    """A generic model that handles different database entities with dirty-state tracking."""
    def __init__(self, data_list, headers, editable_cols):
        super().__init__()
        self._data = data_list
        # Map nice header names to object attribute names
        self._headers = headers
        self._editable_cols = editable_cols
        self.dirty_rows = set()
        
        # Attribute Mapping (Headers -> Attr Name)
        self._attr_map = {
            "ID": "id",
            "Series ID": "series_id",
            "Episode ID": "episode_id",
            "Show ID": "show_id",
            "S": "season_number",
            "E": "episode_number",
            "Title": "title",
            "Name": "name",
            "Show Name": "show_name",
            "Filename": "filename",
            "Path": "path",
            "Thumbnail Path": "thumbnail_path",
            "Thumbnail URL": "thumbnail_url",
            "Local Path": "local_path",
            "Status": "status",
            "Progress": "progress",
            "Timestamp": "timestamp",
            "Completed": "completed",
            "Date Added": "date_added",
            "Last Watched": "last_watched",
            "Speed": "speed",
            "ETA": "eta",
            "AniList ID": "anilist_id",
            "Notes": "notes",
            "Index": "index",
            "Type": "type",
            "Codec": "codec",
            "Language": "language",
            "Sub Index": "sub_index"
        }

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        item = self._data[row]

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            header = self._headers[col]
            attr = self._attr_map.get(header, header.lower().replace(" ", "_"))
            
            # Special case for MediaTrack stream_index which is internal 'index'
            if isinstance(item, MediaTrack) and attr == "index":
                val = item.index
            else:
                val = getattr(item, attr, "N/A")
                
            if isinstance(val, (list, dict)):
                return json.dumps(val)
            if header == "Completed":
                return "Yes" if val else "No"
            return str(val) if val is not None else ""
        
        if role == Qt.ItemDataRole.BackgroundRole:
            if row in self.dirty_rows:
                return QColor(255, 255, 200) # Yellow for edited
        
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.isValid() and role == Qt.ItemDataRole.EditRole:
            row = index.row()
            col = index.column()
            item = self._data[row]
            
            if col not in self._editable_cols:
                return False
                
            header = self._headers[col]
            attr = self._attr_map.get(header, header.lower().replace(" ", "_"))
            
            try:
                current_val = getattr(item, attr)
                if isinstance(current_val, int):
                    value = int(value)
                elif isinstance(current_val, float):
                    value = float(value)
                elif isinstance(current_val, bool):
                    value = value.lower() in ['yes', 'true', '1', 'y']
                elif isinstance(current_val, list):
                    value = json.loads(value)
            except (ValueError, json.JSONDecodeError, AttributeError):
                # If attribute doesn't exist or cast fails, just keep as string or fail
                pass
                
            setattr(item, attr, value)
            self.dirty_rows.add(row)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole])
            return True
        return False

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        if index.column() in self._editable_cols:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

class DatabaseBrowser(QDialog):
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("Database Browser")
        self.resize(1300, 850)
        self.setup_ui()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Toolbar
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.main_layout.addWidget(self.toolbar)
        
        self.refresh_action = QAction("Refresh", self)
        self.refresh_action.triggered.connect(self.load_data)
        self.toolbar.addAction(self.refresh_action)
        self.toolbar.addSeparator()
        
        self.write_action = QAction("Write Changes", self)
        self.write_action.triggered.connect(self.commit_changes)
        self.toolbar.addAction(self.write_action)
        
        self.revert_action = QAction("Revert Changes", self)
        self.revert_action.triggered.connect(self.load_data)
        self.toolbar.addAction(self.revert_action)
        self.toolbar.addSeparator()
        
        self.add_action = QAction("Add Row", self)
        self.add_action.triggered.connect(self.add_row)
        self.toolbar.addAction(self.add_action)
        
        self.delete_action = QAction("Delete Row", self)
        self.delete_action.triggered.connect(self.delete_row)
        self.toolbar.addAction(self.delete_action)
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Filter current table...")
        self.search_bar.setFixedWidth(250)
        self.search_bar.textChanged.connect(self.apply_filter)
        self.toolbar.addWidget(QLabel(" Filter: "))
        self.toolbar.addWidget(self.search_bar)
        
        self.regex_check = QCheckBox("Regex")
        self.regex_check.stateChanged.connect(lambda: self.apply_filter(self.search_bar.text()))
        self.toolbar.addWidget(self.regex_check)
        
        # Content
        self.content_layout = QHBoxLayout()
        self.main_layout.addLayout(self.content_layout)
        
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
        self.table_names = ["Series", "Episodes", "Watch Progress", "Media Tracks", "Online Progress", "Downloads", "Planner"]
        self.sidebar.addItems(self.table_names)
        self.sidebar.currentRowChanged.connect(self.switch_table)
        self.content_layout.addWidget(self.sidebar)
        
        self.stack = QStackedWidget()
        self.content_layout.addWidget(self.stack)
        
        self.views = []
        self.proxies = []
        self.models = [None] * len(self.table_names)
        
        for i in range(len(self.table_names)):
            container = QWidget()
            v_layout = QVBoxLayout(container)
            view = QTableView()
            view.setAlternatingRowColors(True)
            view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            proxy = QSortFilterProxyModel()
            view.setModel(proxy)
            v_layout.addWidget(view)
            
            if i == 1: # Episodes extra tools
                tools = QHBoxLayout()
                btn1 = QPushButton("✨ Auto-Titles")
                btn1.clicked.connect(self.bulk_generate_titles)
                btn2 = QPushButton("🧠 Smart Extract")
                btn2.clicked.connect(self.bulk_extract_titles)
                tools.addWidget(btn1)
                tools.addWidget(btn2)
                tools.addStretch()
                v_layout.insertLayout(0, tools)
            
            self.views.append(view)
            self.proxies.append(proxy)
            self.stack.addWidget(container)
        
        self.status_bar = QStatusBar()
        self.main_layout.addWidget(self.status_bar)
        
        self.sidebar.setCurrentRow(0)
        QTimer.singleShot(100, self.load_data)

    def switch_table(self, index):
        self.stack.setCurrentIndex(index)
        self.apply_filter(self.search_bar.text())
        
    def apply_filter(self, text):
        idx = self.stack.currentIndex()
        if idx < 0 or idx >= len(self.proxies): return
        proxy = self.proxies[idx]
        
        if self.regex_check.isChecked():
            proxy.setFilterRegularExpression(text)
        else:
            proxy.setFilterFixedString(text)
        proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        proxy.setFilterKeyColumn(-1)

    @qasync.asyncSlot()
    async def load_data(self):
        self.status_bar.showMessage("Syncing with database...")
        
        # Fetch data for all tables
        data_futures = [
            self.db.get_all_series(),
            self.db.get_all_episodes(),
            self.db.get_all_progress(),
            self.db.get_all_media_tracks(),
            self.db.get_all_online_progress(),
            self.db.get_all_download_tasks(),
            self.db.get_all_planner_entries()
        ]
        results = await asyncio.gather(*data_futures)
        
        # Headers and Editable Columns
        configs = [
            (["ID", "Name", "Path", "Thumbnail Path", "Date Added"], [1, 2, 3]),
            (["ID", "Series ID", "Title", "S", "E", "Filename", "Path"], [2, 3, 4]),
            (["ID", "Episode ID", "Timestamp", "Completed", "Last Watched"], [2, 3]),
            (["ID", "Episode ID", "Index", "Type", "Codec", "Language", "Title", "Sub Index"], []),
            (["ID", "Show ID", "Show Name", "E", "Timestamp", "Completed", "Last Watched", "Local Path"], [2, 3, 4, 5, 7]),
            (["ID", "Filename", "Status", "Progress", "Speed", "ETA"], []),
            (["ID", "Show ID", "Show Name", "Status", "Notes", "AniList ID"], [1, 2, 3, 4, 5])
        ]
        
        for i, data in enumerate(results):
            headers, edit_cols = configs[i]
            model = GenericTableModel(data, headers, edit_cols)
            self.models[i] = model
            self.proxies[i].setSourceModel(model)
            
            header_view = self.views[i].horizontalHeader()
            header_view.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            if i == 2 or i == 5: # Watch Progress and Downloads stretch
                header_view.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            else:
                header_view.setStretchLastSection(True)

        self.status_bar.showMessage("Database Browser Ready", 3000)

    @qasync.asyncSlot()
    async def commit_changes(self):
        self.status_bar.showMessage("Committing changes...")
        count = 0
        
        # Define commit logic per table
        for i, model in enumerate(self.models):
            if not model or not model.dirty_rows: continue
            
            for row in model.dirty_rows:
                item = model._data[row]
                try:
                    if i == 0: # Series
                        if item.id is None: await self.db.add_series(item)
                        else: await self.db.update_series_metadata(item)
                    elif i == 1: # Episodes
                        if item.id is None: await self.db.add_episode(item)
                        else: await self.db.update_episode_metadata(item)
                    elif i == 2: # Progress
                        await self.db.update_progress(item)
                    elif i == 3: # Media Tracks
                        await self.db.update_media_track(item)
                    elif i == 4: # Online Progress
                        await self.db.update_online_progress(item)
                    elif i == 5: # Downloads
                        await self.db.update_download_task(item)
                    elif i == 6: # Planner
                        if item.id is None: await self.db.add_planner_entry(item)
                        else: await self.db.update_planner_entry(item)
                    count += 1
                except Exception as e:
                    print(f"Error saving row {row} in table {self.table_names[i]}: {e}")
            model.dirty_rows.clear()
            
        await self.load_data()
        self.status_bar.showMessage(f"Saved {count} changes to local database", 5000)

    def add_row(self):
        idx = self.stack.currentIndex()
        model = self.models[idx]
        if not model: return
        
        # Default Item Creation
        new_item = None
        if idx == 0: new_item = Series(name="New Series", path="...")
        elif idx == 1: new_item = Episode(series_id=1, filename="...", path="...")
        elif idx == 4: new_item = OnlineProgress(show_id="new", show_name="New Show", episode_number=1)
        elif idx == 6: new_item = PlannerEntry(show_name="New Entry", status="Plan to Watch")
        
        if new_item:
            model.beginInsertRows(QModelIndex(), len(model._data), len(model._data))
            model._data.append(new_item)
            model.endInsertRows()
            model.dirty_rows.add(len(model._data) - 1)

    @qasync.asyncSlot()
    async def delete_row(self):
        idx = self.stack.currentIndex()
        view = self.views[idx]
        selection = view.selectionModel().selectedRows()
        if not selection: return
        
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete {len(selection)} selected row(s)?", 
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        
        # This implementation requires specific delete methods in DatabaseManager
        # which we might not have for all tables yet.
        QMessageBox.warning(self, "Safe Guard", "Direct deletion from Browser is limited to avoid breaking database integrity.")

    @qasync.asyncSlot()
    async def bulk_generate_titles(self):
        proxy = self.proxies[1]
        model = self.models[1]
        for i in range(proxy.rowCount()):
            idx = proxy.mapToSource(proxy.index(i, 0)).row()
            ep = model._data[idx]
            s = ep.season_number or 1
            e = ep.episode_number or (i + 1)
            ep.title = f"Season {s}: Episode {e}"
            model.dirty_rows.add(idx)
        model.layoutChanged.emit()

    @qasync.asyncSlot()
    async def bulk_extract_titles(self):
        proxy = self.proxies[1]
        model = self.models[1]
        for i in range(proxy.rowCount()):
            idx = proxy.mapToSource(proxy.index(i, 0)).row()
            ep = model._data[idx]
            extracted = TitleExtractor.extract(ep.filename)
            if extracted:
                ep.title = extracted
                model.dirty_rows.add(idx)
        model.layoutChanged.emit()
