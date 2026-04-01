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
from PyQt6.QtGui import QPixmap
from ..database.models import PlannerEntry
import qasync
import logging
import httpx
from pathlib import Path
import hashlib
from ..utils import anilist_client
 

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
        # Subtitle (AniList display title / native)
        self.subtitle_label = QLabel("")
        self.subtitle_label.setStyleSheet("color: #bbb; font-size: 9pt;")
        self.subtitle_label.setWordWrap(True)
        
        self.status_label = QLabel(self.entry.status)
        self.status_label.setObjectName("status")
        self._update_status_style()
        
        self.header_layout.addWidget(self.name_label, 1)
        self.header_layout.addWidget(self.subtitle_label, 1)
        self.header_layout.addWidget(self.status_label)

        # Content: left cover, right column with header, metadata, badges, description
        self.content_layout = QHBoxLayout()

        # Cover placeholder (larger)
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(96, 144)
        self.cover_label.setStyleSheet("border-radius:6px; background-color: #0f0f0f;")
        self.content_layout.addWidget(self.cover_label)

        # Right column
        self.right_col = QVBoxLayout()
        self.right_col.addLayout(self.header_layout)

        # ID / search row
        self.meta_row = QHBoxLayout()
        if self.entry.show_id:
            self.id_label = QLabel(f"ID: {self.entry.show_id}")
            self.id_label.setObjectName("id_label")
            self.meta_row.addWidget(self.id_label)
            self.search_btn = QPushButton("🔍 Find Online")
            self.search_btn.setObjectName("search_btn")
            self.search_btn.clicked.connect(lambda: self.search_requested.emit(self.entry.show_id, self.entry.show_name))
            self.meta_row.addWidget(self.search_btn)
        self.meta_row.addStretch()
        self.right_col.addLayout(self.meta_row)

        # Badge area (episodes, score, next ep)
        self.badge_layout = QHBoxLayout()
        self.badge_layout.setSpacing(8)
        self.right_col.addLayout(self.badge_layout)

        self.content_layout.addLayout(self.right_col, 1)
        self.main_layout.addLayout(self.content_layout)

        # Description (short) under badges
        self.description_label = QLabel("")
        self.description_label.setObjectName("desc")
        self.description_label.setStyleSheet("color: #999; font-size: 9pt;")
        self.description_label.setWordWrap(True)
        self.description_label.setMaximumHeight(90)
        self.main_layout.addWidget(self.description_label)

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
        # Start AniList enrichment after UI is ready
        try:
            anilist_id = getattr(self.entry, 'anilist_id', None)
            if anilist_id:
                asyncio.create_task(self._enrich_from_anilist(int(anilist_id)))
        except Exception:
            pass

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

    async def _enrich_from_anilist(self, anilist_id: int):
        try:
            data = await anilist_client.get_by_id(anilist_id)
            if not data:
                return

            # Update badges
            def add_badge(text):
                lbl = QLabel(text)
                lbl.setStyleSheet('background-color: #222; color: #ddd; padding:4px 8px; border-radius:6px;')
                self.badge_layout.addWidget(lbl)

            if data.get('episodes'):
                add_badge(f"Ep: {data['episodes']}")
            if data.get('average_score') is not None:
                add_badge(f"★ {data['average_score']:.1f}")
            if data.get('next_episode'):
                seconds = data.get('next_episode_airing') or 0
                if seconds > 0:
                    add_badge(f"Next in {self._format_seconds(seconds)} (Ep {data.get('next_episode')})")

            # Genres badge (compact)
            genres = data.get('genres') or []
            if genres:
                add_badge("/".join(genres[:4]))

            # Subtitle / titles
            display = data.get('display_title') or ''
            native = data.get('title_native') or ''
            sub_text = display
            if native and native != display:
                sub_text = f"{display} — {native}"
            self.subtitle_label.setText(sub_text)

            # Description (trimmed)
            desc = data.get('description') or ""
            if desc:
                if len(desc) > 400:
                    desc = desc[:400].rsplit(' ', 1)[0] + '…'
                self.description_label.setText(desc)

            # Cover image with disk cache
            cover = data.get('cover_url')
            if cover:
                try:
                    # derive cache path
                    ws_root = Path(__file__).resolve().parents[2]
                    thumb_dir = ws_root / 'cache' / 'thumbnails'
                    thumb_dir.mkdir(parents=True, exist_ok=True)
                    # filename by anilist id when available, otherwise hash the URL
                    if data.get('anilist_id'):
                        ext = Path(cover).suffix or '.jpg'
                        fname = f"{data.get('anilist_id')}{ext}"
                    else:
                        h = hashlib.sha1(cover.encode('utf-8')).hexdigest()
                        ext = Path(cover).suffix or '.jpg'
                        fname = f"{h}{ext}"
                    fp = thumb_dir / fname
                    if fp.exists():
                        pix = QPixmap(str(fp))
                        if not pix.isNull():
                            self.cover_label.setPixmap(pix.scaled(self.cover_label.width(), self.cover_label.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    else:
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            resp = await client.get(cover)
                            resp.raise_for_status()
                            # write bytes and load
                            try:
                                with open(fp, 'wb') as f:
                                    f.write(resp.content)
                            except Exception:
                                pass
                            pix = QPixmap()
                            pix.loadFromData(resp.content)
                            if not pix.isNull():
                                self.cover_label.setPixmap(pix.scaled(self.cover_label.width(), self.cover_label.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                except Exception as e:
                    logger.debug(f"Failed to load/save AniList cover: {e}")
        except Exception as e:
            logger.debug(f"AniList enrichment failed for {anilist_id}: {e}")

    def _format_seconds(self, s: int) -> str:
        # Simple human-friendly duration
        days = s // 86400
        s %= 86400
        hours = s // 3600
        mins = (s % 3600) // 60
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if mins and not days:
            parts.append(f"{mins}m")
        return ' '.join(parts) if parts else 'now'

class PlannerEntryDialog(QDialog):
    def __init__(self, parent=None, entry=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle("Plan New Show" if not entry else f"Edit {entry.show_name}")
        self.setMinimumWidth(450)
        self.setup_ui()
        self._selected_anilist = None

    def setup_ui(self):
        self.layout = QFormLayout(self)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(20, 20, 20, 20)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Frieren: Beyond Journey's End")
        self.name_input.setFixedHeight(35)
        if self.entry:
            self.name_input.setText(self.entry.show_name)
        
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("Optional (the part after /anime/ in the URL)")
        self.id_input.setFixedHeight(35)
        if self.entry:
            self.id_input.setText(self.entry.show_id or "")

        # Add AniList search button next to ID input
        self.find_btn = QPushButton("🔎 Find on AniList")
        self.find_btn.setFixedHeight(35)
        self.find_btn.setObjectName("search_btn")
        self.find_btn.clicked.connect(self._on_find_clicked)

        id_row_widget = QWidget()
        id_row_layout = QHBoxLayout(id_row_widget)
        id_row_layout.setContentsMargins(0,0,0,0)
        id_row_layout.addWidget(self.id_input)
        id_row_layout.addWidget(self.find_btn)
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Plan to Watch", "Watching", "Finished", "Dropped", "On Hold"])
        self.status_combo.setFixedHeight(35)
        if self.entry:
            self.status_combo.setCurrentText(self.entry.status)
        
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Any reminders or why you want to watch this...")
        self.notes_input.setMaximumHeight(100)
        self.notes_input.setStyleSheet("padding: 8px;")
        if self.entry:
            self.notes_input.setText(self.entry.notes)

        self.layout.addRow("Series Name:", self.name_input)
        self.layout.addRow("AllAnime ID:", id_row_widget)
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
        data = {
            "show_name": self.name_input.text().strip(),
            "show_id": self.id_input.text().strip() if self.id_input.text().strip() else None,
            "status": self.status_combo.currentText(),
            "notes": self.notes_input.toPlainText().strip()
        }
        if self._selected_anilist:
            # Merge AniList enrichment fields
            data.update({
                "anilist_id": self._selected_anilist.get('anilist_id'),
                "cover_url": self._selected_anilist.get('cover_url'),
                "episodes": self._selected_anilist.get('episodes'),
                "average_score": self._selected_anilist.get('average_score'),
                "next_episode": self._selected_anilist.get('next_episode'),
                "next_episode_airing": self._selected_anilist.get('next_episode_airing'),
            })
        return data

    def _on_find_clicked(self):
        dlg = AniListSearchDialog(self)
        if dlg.exec():
            sel = getattr(dlg, 'selected', None)
            if sel:
                # populate fields
                self.name_input.setText(sel.get('display_title') or sel.get('title_romaji') or sel.get('title_english') or "")
                self.id_input.setText(str(sel.get('anilist_id')))
                self._selected_anilist = sel


class AniListSearchDialog(QDialog):
    """Dialog to search AniList and pick a result."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find on AniList")
        self.setMinimumWidth(600)
        self.selected = None
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search AniList...")
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self._do_search_sync)
        top.addWidget(self.search_input)
        top.addWidget(self.search_btn)
        self.layout.addLayout(top)

        self.results_area = QScrollArea()
        self.results_area.setWidgetResizable(True)
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.results_area.setWidget(self.results_widget)
        self.layout.addWidget(self.results_area)

        self.cancel_btn = QPushButton("Close")
        self.cancel_btn.clicked.connect(self.reject)
        self.layout.addWidget(self.cancel_btn)

    def _do_search_sync(self):
        query = self.search_input.text().strip()
        if not query:
            return
        # Clear old
        while self.results_layout.count():
            it = self.results_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        try:
            # Use synchronous HTTP client here to avoid creating asyncio tasks
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    anilist_client._ENDPOINT,
                    headers=anilist_client._HEADERS,
                    json={"query": anilist_client._SEARCH_QUERY, "variables": {"search": query, "page": 1}},
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("data", {}).get("Page", {}).get("media") or []

            for it in items:
                row = QWidget()
                rl = QHBoxLayout(row)
                cover = QLabel()
                cover.setFixedSize(48,72)
                if it.get('coverImage'):
                    try:
                        img_url = it['coverImage'].get('large') or it['coverImage'].get('medium')
                        if img_url:
                            r = httpx.get(img_url, timeout=8.0)
                            if r.status_code == 200:
                                pix = QPixmap()
                                pix.loadFromData(r.content)
                                cover.setPixmap(pix.scaled(48,72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    except Exception:
                        pass
                rl.addWidget(cover)
                title = (it.get('title') or {}).get('english') or (it.get('title') or {}).get('romaji') or ''
                info = QLabel(f"{title}\nEpisodes: {it.get('episodes') or '??'}  Score: {it.get('averageScore') or 'N/A'}")
                info.setWordWrap(True)
                rl.addWidget(info, 1)
                sel_btn = QPushButton("Select")
                try:
                    logger.debug("AniList raw item type=%s", type(it))
                    logger.debug("AniList raw item: %r", it)
                    parsed_item = anilist_client._parse_media(it) if isinstance(it, dict) else {"anilist_id": None, "display_title": str(it)}
                except Exception as e:
                    logger.exception("Failed to parse AniList item: %s", e)
                    parsed_item = {"anilist_id": None, "display_title": str(it)}
                def _select(_checked=None, x=parsed_item):
                    logger.debug("AniList selected: %r", x)
                    self.selected = x
                    self.accept()
                sel_btn.clicked.connect(_select)
                rl.addWidget(sel_btn)
                self.results_layout.addWidget(row)
        except Exception as e:
            logger.error(f"AniList search failed: {e}")

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
            # AniList enrichment fields (may be missing)
            entry.anilist_id = data.get('anilist_id') if data.get('anilist_id') is not None else getattr(entry, 'anilist_id', None)
            entry.cover_url = data.get('cover_url') if data.get('cover_url') is not None else getattr(entry, 'cover_url', None)
            entry.episodes = data.get('episodes') if data.get('episodes') is not None else getattr(entry, 'episodes', None)
            entry.average_score = data.get('average_score') if data.get('average_score') is not None else getattr(entry, 'average_score', None)
            entry.next_episode = data.get('next_episode') if data.get('next_episode') is not None else getattr(entry, 'next_episode', None)
            entry.next_episode_airing = data.get('next_episode_airing') if data.get('next_episode_airing') is not None else getattr(entry, 'next_episode_airing', None)
            
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
