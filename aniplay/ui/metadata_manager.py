from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QTableView, QPushButton, QHeaderView, QAbstractItemView,
                             QMessageBox, QLineEdit, QLabel, QWidget)
from PyQt6.QtCore import Qt, QAbstractTableModel, pyqtSignal, QModelIndex, QTimer
import qasync
import asyncio
from ..database.db import DatabaseManager
from ..database.models import Series, Episode, WatchProgress
from ..utils.title_extractor import TitleExtractor

class SeriesTableModel(QAbstractTableModel):
    def __init__(self, series_list):
        super().__init__()
        self._series = series_list
        self._headers = ["ID", "Name", "Path", "Thumbnail", "Date Added"]

    def rowCount(self, parent=QModelIndex()):
        return len(self._series)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        
        series = self._series[index.row()]
        col = index.column()
        if col == 0: return series.id
        if col == 1: return series.name
        if col == 2: return series.path
        if col == 3: return series.thumbnail_path
        if col == 4: return str(series.date_added)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        # Allow editing certain columns
        if index.column() in [1, 2, 3]:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

class EpisodesTableModel(QAbstractTableModel):
    def __init__(self, episodes_list):
        super().__init__()
        self._episodes = episodes_list
        self._headers = ["ID", "Series ID", "Title", "S", "E", "Filename", "Path"]

    def rowCount(self, parent=QModelIndex()):
        return len(self._episodes)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        
        ep = self._episodes[index.row()]
        col = index.column()
        if col == 0: return ep.id
        if col == 1: return ep.series_id
        if col == 2: return ep.title or ""
        if col == 3: return ep.season_number
        if col == 4: return ep.episode_number
        if col == 5: return ep.filename
        if col == 6: return ep.path
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        # Allow editing title, season, episode
        if index.column() in [2, 3, 4]:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

class WatchProgressTableModel(QAbstractTableModel):
    def __init__(self, progress_list):
        super().__init__()
        self._progress = progress_list
        self._headers = ["ID", "Episode ID", "Timestamp", "Completed", "Last Watched"]

    def rowCount(self, parent=QModelIndex()):
        return len(self._progress)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        
        p = self._progress[index.row()]
        col = index.column()
        if col == 0: return p.id
        if col == 1: return p.episode_id
        if col == 2: return p.timestamp
        if col == 3: return "Yes" if p.completed else "No"
        if col == 4: return str(p.last_watched)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return None

class MetadataManager(QDialog):
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("Metadata Manager")
        self.resize(1000, 700)
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        
        # Tabs
        self.series_tab = QWidget()
        self.episodes_tab = QWidget()
        self.progress_tab = QWidget()
        
        self.tabs.addTab(self.series_tab, "Series")
        self.tabs.addTab(self.episodes_tab, "Episodes")
        self.tabs.addTab(self.progress_tab, "Watch Progress")
        
        self.layout.addWidget(self.tabs)
        
        self.setup_series_tab()
        self.setup_episodes_tab()
        self.setup_progress_tab()
        
        # Bottom Buttons
        self.buttons = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_data)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        
        self.buttons.addWidget(self.refresh_btn)
        self.buttons.addStretch()
        self.buttons.addWidget(self.close_btn)
        self.layout.addLayout(self.buttons)

        # Load data initially
        QTimer.singleShot(100, self.load_data)

    def setup_series_tab(self):
        layout = QVBoxLayout(self.series_tab)
        self.series_view = QTableView()
        self.series_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.series_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.series_view)
        
        # Help label
        layout.addWidget(QLabel("Double-click Name, Path or Thumbnail to edit directly (changes NOT yet saved automatically)."))
        
        # Buttons
        btns = QHBoxLayout()
        self.save_series_btn = QPushButton("Save Changes (N/A)")
        self.save_series_btn.setEnabled(False)
        btns.addStretch()
        btns.addWidget(self.save_series_btn)
        layout.addLayout(btns)

    def setup_episodes_tab(self):
        layout = QVBoxLayout(self.episodes_tab)
        
        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.ep_search = QLineEdit()
        self.ep_search.textChanged.connect(self.filter_episodes)
        search_layout.addWidget(self.ep_search)
        layout.addLayout(search_layout)
        
        self.episodes_view = QTableView()
        self.episodes_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.episodes_view)
        
        # Episode Editing Controls
        edit_group = QHBoxLayout()
        self.ep_title_edit = QLineEdit()
        self.ep_title_edit.setPlaceholderText("New Episode Title")
        self.apply_ep_title_btn = QPushButton("Update Title")
        self.apply_ep_title_btn.clicked.connect(self.update_selected_episode_title)
        
        edit_group.addWidget(QLabel("Selected Title:"))
        edit_group.addWidget(self.ep_title_edit)
        edit_group.addWidget(self.apply_ep_title_btn)
        
        self.bulk_gen_btn = QPushButton("✨ Auto-Generate Titles")
        self.bulk_gen_btn.setToolTip("Generate 'Season X: Episode Y' titles for all episodes in current view.")
        self.bulk_gen_btn.clicked.connect(self.bulk_generate_titles)
        
        self.smart_gen_btn = QPushButton("🧠 Smart Extract")
        self.smart_gen_btn.setToolTip("Extract titles from filenames based on detected patterns.")
        self.smart_gen_btn.clicked.connect(self.bulk_extract_titles)
        
        edit_group.addWidget(self.bulk_gen_btn)
        edit_group.addWidget(self.smart_gen_btn)
        
        layout.addLayout(edit_group)

    def setup_progress_tab(self):
        layout = QVBoxLayout(self.progress_tab)
        self.progress_view = QTableView()
        self.progress_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.progress_view)
        
        btns = QHBoxLayout()
        self.delete_progress_btn = QPushButton("Delete Selected Progress")
        self.delete_progress_btn.clicked.connect(self.delete_selected_progress)
        btns.addStretch()
        btns.addWidget(self.delete_progress_btn)
        layout.addLayout(btns)

    @qasync.asyncSlot()
    async def load_data(self):
        series = await self.db.get_all_series()
        self.series_model = SeriesTableModel(series)
        self.series_view.setModel(self.series_model)
        
        episodes = await self.db.get_all_episodes()
        self.all_episodes = episodes
        self.episodes_model = EpisodesTableModel(episodes)
        self.episodes_view.setModel(self.episodes_model)
        self.episodes_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.episodes_view.horizontalHeader().setStretchLastSection(True)
        
        # Load progress
        progress_items = await self.db.get_all_progress()
        self.progress_model = WatchProgressTableModel(progress_items)
        self.progress_view.setModel(self.progress_model)
        self.progress_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def filter_episodes(self, text):
        if not hasattr(self, 'all_episodes'): return
        filtered = [ep for ep in self.all_episodes if text.lower() in ep.filename.lower() or (ep.title and text.lower() in ep.title.lower())]
        self.episodes_model = EpisodesTableModel(filtered)
        self.episodes_view.setModel(self.episodes_model)

    @qasync.asyncSlot()
    async def update_selected_episode_title(self):
        selection = self.episodes_view.selectionModel().selectedRows()
        if not selection:
            QMessageBox.warning(self, "No Selection", "Please select an episode from the table.")
            return
            
        new_title = self.ep_title_edit.text()
        if not new_title:
            return
            
        row = selection[0].row()
        episode = self.episodes_model._episodes[row]
        
        episode.title = new_title
        await self.db.update_episode_metadata(episode)
        
        # Refresh current view
        await self.load_data()
        self.ep_title_edit.clear()

    @qasync.asyncSlot()
    async def bulk_generate_titles(self):
        # Current view episodes
        episodes = self.episodes_model._episodes
        if not episodes: return
        
        missing = [ep for ep in episodes if not ep.title]
        
        if not missing:
            reply = QMessageBox.question(self, "Bulk Generate", 
                                       "All episodes in view already have titles. Do you want to overwrite ALL of them with generic titles?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                targets = episodes
            else:
                return
        else:
            msg = f"Found {len(missing)} episodes without titles.\n\nDo you want to generated generic titles for these missing ones?\n\n(Choose 'No' to overwrite ALL {len(episodes)} episodes instead)"
            reply = QMessageBox.question(self, "Bulk Generate", msg,
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            
            if reply == QMessageBox.StandardButton.Yes:
                targets = missing
            elif reply == QMessageBox.StandardButton.No:
                targets = episodes
            else:
                return
            
        for ep in targets:
            s = ep.season_number if ep.season_number is not None else 1
            e = ep.episode_number if ep.episode_number is not None else 1
            ep.title = f"Season {s}: Episode {e}"
            await self.db.update_episode_metadata(ep)
            
        await self.load_data()
        QMessageBox.information(self, "Done", f"Generic titles applied to {len(targets)} episodes.")

    @qasync.asyncSlot()
    async def bulk_extract_titles(self):
        episodes = self.episodes_model._episodes
        if not episodes: return
        
        missing = [ep for ep in episodes if not ep.title]
        
        if not missing:
            reply = QMessageBox.question(self, "Smart Extract", 
                                       "All episodes already have titles. Do you want to try re-extracting and potentially overwriting ALL of them?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                targets = episodes
            else:
                return
        else:
            msg = f"Found {len(missing)} episodes without titles.\n\nDo you want to attempt smart extraction from filenames for these missing ones?\n\n(Choose 'No' to try re-extracting for ALL {len(episodes)} episodes instead)"
            reply = QMessageBox.question(self, "Smart Extract", msg,
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            
            if reply == QMessageBox.StandardButton.Yes:
                targets = missing
            elif reply == QMessageBox.StandardButton.No:
                targets = episodes
            else:
                return
            
        count = 0
        for ep in targets:
            extracted = TitleExtractor.extract(ep.filename)
            if extracted:
                s = ep.season_number if ep.season_number is not None else 1
                ep.title = f"Season {s}: {extracted}"
                await self.db.update_episode_metadata(ep)
                count += 1
            
        await self.load_data()
        QMessageBox.information(self, "Done", f"Successfully extracted titles for {count} out of {len(targets)} attempted episodes.")

    @qasync.asyncSlot()
    async def delete_selected_progress(self):
        selection = self.progress_view.selectionModel().selectedRows()
        if not selection:
            return
            
        # This needs mark_episode_watched(..., False) or a direct delete
        for index in selection:
            progress = self.progress_model._progress[index.row()]
            await self.db.mark_episode_watched(progress.episode_id, False)
            
        await self.load_data()
