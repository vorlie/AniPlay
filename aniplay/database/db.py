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

import aiosqlite
#import sqlite3
from typing import List, Optional, Any  # noqa: F401
from datetime import datetime
from .models import Series, Episode, WatchProgress, MediaTrack, OnlineProgress, DownloadTaskState, PlannerEntry
from ..config import DB_PATH
from ..utils.logger import get_logger

logger = get_logger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        logger.debug(f"DatabaseManager initialized with path: {self.db_path}")

    async def initialize(self):
        logger.info("Initializing database...")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            
            # Series table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS series (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    thumbnail_path TEXT,
                    rpc_image_url TEXT,
                    size_bytes INTEGER DEFAULT 0,
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Episodes table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    series_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    title TEXT,
                    duration REAL DEFAULT 0,
                    size_bytes INTEGER DEFAULT 0,
                    episode_number INTEGER,
                    season_number INTEGER,
                    folder_name TEXT,
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (series_id) REFERENCES series (id) ON DELETE CASCADE
                )
            """)
            
            # Watch progress table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS watch_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id INTEGER NOT NULL UNIQUE,
                    timestamp REAL DEFAULT 0,
                    last_watched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed BOOLEAN DEFAULT 0,
                    FOREIGN KEY (episode_id) REFERENCES episodes (id) ON DELETE CASCADE
                )
            """)
            # Media tracks table (audio/subs/video)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS media_tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id INTEGER NOT NULL,
                    stream_index INTEGER NOT NULL,
                    track_type TEXT NOT NULL,
                    codec TEXT,
                    language TEXT,
                    title TEXT,
                    sub_index INTEGER,
                    FOREIGN KEY (episode_id) REFERENCES episodes (id) ON DELETE CASCADE
                )
            """)
            
            # Online progress table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS online_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    show_id TEXT NOT NULL,
                    show_name TEXT NOT NULL,
                    episode_number INTEGER NOT NULL,
                    timestamp REAL DEFAULT 0,
                    thumbnail_url TEXT,
                    local_path TEXT,
                    completed BOOLEAN DEFAULT 0,
                    last_watched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    allmanga_id TEXT,
                    nyaa_query TEXT,
                    UNIQUE(show_id, episode_number)
                )
            """)
            
            # Download Tasks table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS download_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL UNIQUE,
                    url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL DEFAULT 0.0,
                    speed TEXT,
                    eta TEXT,
                    elapsed TEXT,
                    referrer TEXT,
                    metadata_json TEXT DEFAULT '{}',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Planner table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS planner (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    show_id TEXT,
                    show_name TEXT NOT NULL,
                    status TEXT DEFAULT 'Plan to Watch',
                    notes TEXT,
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            async with db.execute("PRAGMA table_info(episodes)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
                if 'folder_name' not in columns:
                    await db.execute("ALTER TABLE episodes ADD COLUMN folder_name TEXT")
                if 'title' not in columns:
                    await db.execute("ALTER TABLE episodes ADD COLUMN title TEXT")
                if 'size_bytes' not in columns:
                    await db.execute("ALTER TABLE episodes ADD COLUMN size_bytes INTEGER DEFAULT 0")
            
            async with db.execute("PRAGMA table_info(series)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
                if 'rpc_image_url' not in columns:
                    await db.execute("ALTER TABLE series ADD COLUMN rpc_image_url TEXT")
                if 'size_bytes' not in columns:
                    await db.execute("ALTER TABLE series ADD COLUMN size_bytes INTEGER DEFAULT 0")
            
            # Add timestamp to online_progress if it doesn't exist
            async with db.execute("PRAGMA table_info(online_progress)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
                if 'timestamp' not in columns:
                    await db.execute("ALTER TABLE online_progress ADD COLUMN timestamp REAL DEFAULT 0.0")
                if 'thumbnail_url' not in columns:
                    await db.execute("ALTER TABLE online_progress ADD COLUMN thumbnail_url TEXT")
                # Migration: Add allmanga_id to online_progress if it doesn't exist
                try:
                    await db.execute("ALTER TABLE online_progress ADD COLUMN allmanga_id TEXT")
                    logger.info("Database: Added allmanga_id column to online_progress")
                except Exception:
                    pass # Column already exists
                try:
                    await db.execute("ALTER TABLE online_progress ADD COLUMN nyaa_query TEXT")
                    logger.info("Database: Added nyaa_query column to online_progress")
                except Exception:
                    pass # Column already exists
                if 'local_path' not in columns:
                    await db.execute("ALTER TABLE online_progress ADD COLUMN local_path TEXT")
            
            await db.commit()

    # Series Operations
    
    async def add_series(self, series: Series) -> int:
        logger.debug(f"Adding series: {series.name} (path: {series.path})")
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT OR IGNORE INTO series (name, path, thumbnail_path, rpc_image_url, size_bytes) VALUES (?, ?, ?, ?, ?)",
                (series.name, series.path, series.thumbnail_path, series.rpc_image_url, series.size_bytes)
            )
            await db.commit()
            if cursor.lastrowid:
                series.id = cursor.lastrowid
                logger.info(f"New series added: {series.name} (ID: {series.id})")
                return cursor.lastrowid
            
            # If ignore triggered, find the existing id
            async with db.execute("SELECT id FROM series WHERE path = ?", (series.path,)) as cursor:
                row = await cursor.fetchone()
                series_id = row[0] if row else -1
                logger.debug(f"Series already exists: {series.name} (ID: {series_id})")
                return series_id

    async def get_all_series(self) -> List[Series]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM series ORDER BY name") as cursor:
                rows = await cursor.fetchall()
                logger.debug(f"Fetched {len(rows)} series from database")
                return [Series(
                    id=row['id'],
                    name=row['name'],
                    path=row['path'],
                    thumbnail_path=row['thumbnail_path'],
                    rpc_image_url=row['rpc_image_url'],
                    size_bytes=row['size_bytes'],
                    date_added=datetime.fromisoformat(row['date_added']) if isinstance(row['date_added'], str) else row['date_added']
                ) for row in rows]

    async def get_series(self, series_id: int) -> Optional[Series]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM series WHERE id = ?", (series_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Series(
                        id=row['id'],
                        name=row['name'],
                        path=row['path'],
                        thumbnail_path=row['thumbnail_path'],
                        rpc_image_url=row['rpc_image_url'],
                        size_bytes=row['size_bytes'],
                        date_added=datetime.fromisoformat(row['date_added']) if isinstance(row['date_added'], str) else row['date_added']
                    )
                return None

    async def update_series_poster(self, series_id: int, poster_path: str):
        logger.info(f"Updating poster for series {series_id} to: {poster_path}")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE series SET thumbnail_path = ? WHERE id = ?",
                (poster_path, series_id)
            )
            await db.commit()

    async def update_series_rpc_url(self, series_id: int, rpc_url: str):
        logger.info(f"Updating RPC image URL for series {series_id} to: {rpc_url}")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE series SET rpc_image_url = ? WHERE id = ?",
                (rpc_url, series_id)
            )
            await db.commit()

    async def update_series_size(self, series_id: int, size_bytes: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE series SET size_bytes = ? WHERE id = ?",
                (size_bytes, series_id)
            )
            await db.commit()

    # Episode Operations

    async def add_episode(self, episode: Episode) -> int:
        logger.debug(f"Adding episode: {episode.filename} to series {episode.series_id}")
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT OR IGNORE INTO episodes 
                   (series_id, filename, path, title, duration, size_bytes, episode_number, season_number, folder_name) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (episode.series_id, episode.filename, episode.path, episode.title, episode.duration, 
                 episode.size_bytes, episode.episode_number, episode.season_number, episode.folder_name)
            )
            await db.commit()
            if cursor.lastrowid:
                episode.id = cursor.lastrowid
                logger.info(f"New episode added: {episode.filename} (ID: {episode.id})")
                return cursor.lastrowid
            
            async with db.execute("SELECT id FROM episodes WHERE path = ?", (episode.path,)) as cursor:
                row = await cursor.fetchone()
                ep_id = row[0] if row else -1
                logger.debug(f"Episode already exists: {episode.filename} (ID: {ep_id})")
                return ep_id

    async def update_episode_metadata(self, episode: Episode):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE episodes SET 
                   episode_number = ?, 
                   season_number = ?, 
                   folder_name = ?,
                   title = ?
                   WHERE path = ?""",
                (episode.episode_number, episode.season_number, episode.folder_name, episode.title, episode.path)
            )
            await db.commit()

    async def update_episode_path(self, episode_id: int, new_path: str, new_filename: str, new_folder: Optional[str], new_season: Optional[int]):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE episodes SET 
                   path = ?, 
                   filename = ?, 
                   folder_name = ?,
                   season_number = ?
                   WHERE id = ?""",
                (new_path, new_filename, new_folder, new_season, episode_id)
            )
            await db.commit()

    async def get_all_episodes(self) -> List[Episode]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM episodes") as cursor:
                rows = await cursor.fetchall()
                return [Episode(
                    id=row['id'],
                    series_id=row['series_id'],
                    filename=row['filename'],
                    path=row['path'],
                    title=row['title'],
                    duration=row['duration'],
                    size_bytes=row['size_bytes'],
                    episode_number=row['episode_number'],
                    season_number=row['season_number'],
                    folder_name=row['folder_name']
                ) for row in rows]

    async def update_episode_series(self, episode_id: int, new_series_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE episodes SET series_id = ? WHERE id = ?",
                (new_series_id, episode_id)
            )
            await db.commit()

    async def get_episodes_for_series(self, series_id: int) -> List[Episode]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM episodes WHERE series_id = ? ORDER BY season_number, episode_number, filename", (series_id,)) as cursor:
                rows = await cursor.fetchall()
                return [Episode(
                    id=row['id'],
                    series_id=row['series_id'],
                    filename=row['filename'],
                    path=row['path'],
                    title=row['title'],
                    duration=row['duration'],
                    size_bytes=row['size_bytes'],
                    episode_number=row['episode_number'],
                    season_number=row['season_number'],
                    folder_name=row['folder_name']
                ) for row in rows]

    async def get_episode_by_id(self, episode_id: int) -> Optional[Episode]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Episode(
                        id=row['id'],
                        series_id=row['series_id'],
                        filename=row['filename'],
                        path=row['path'],
                        title=row['title'],
                        duration=row['duration'],
                        size_bytes=row['size_bytes'],
                        episode_number=row['episode_number'],
                        season_number=row['season_number'],
                        folder_name=row['folder_name']
                    )
                return None

    # Media Track Operations

    async def add_media_track(self, track: MediaTrack):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO media_tracks 
                   (episode_id, stream_index, track_type, codec, language, title, sub_index)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (track.episode_id, track.index, track.type, track.codec, track.language, track.title, track.sub_index)
            )
            await db.commit()

    async def clear_episode_tracks(self, episode_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM media_tracks WHERE episode_id = ?", (episode_id,))
            await db.commit()

    async def get_tracks_for_episode(self, episode_id: int) -> List[MediaTrack]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM media_tracks WHERE episode_id = ?", (episode_id,)) as cursor:
                rows = await cursor.fetchall()
                return [MediaTrack(
                    id=row['id'],
                    episode_id=row['episode_id'],
                    index=row['stream_index'],
                    type=row['track_type'],
                    codec=row['codec'],
                    language=row['language'],
                    title=row['title'],
                    sub_index=row['sub_index']
                ) for row in rows]

    async def update_episode_duration(self, episode_id: int, duration: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE episodes SET duration = ? WHERE id = ?", (duration, episode_id))
            await db.commit()

    async def update_episode_size(self, episode_id: int, size_bytes: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE episodes SET size_bytes = ? WHERE id = ?", (size_bytes, episode_id))
            await db.commit()

    # Progress Operations

    async def update_progress(self, progress: WatchProgress):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO watch_progress (episode_id, timestamp, last_watched, completed)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(episode_id) DO UPDATE SET
                   timestamp = excluded.timestamp,
                   last_watched = excluded.last_watched,
                   completed = excluded.completed""",
                (progress.episode_id, progress.timestamp, datetime.now(), int(progress.completed))
            )
            await db.commit()

    async def get_progress(self, episode_id: int) -> Optional[WatchProgress]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM watch_progress WHERE episode_id = ?", (episode_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return WatchProgress(
                        id=row['id'],
                        episode_id=row['episode_id'],
                        timestamp=row['timestamp'],
                        last_watched=datetime.fromisoformat(row['last_watched']) if isinstance(row['last_watched'], str) else row['last_watched'],
                        completed=bool(row['completed'])
                    )
                return None

    async def get_all_progress(self) -> List[WatchProgress]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM watch_progress ORDER BY last_watched DESC") as cursor:
                rows = await cursor.fetchall()
                return [WatchProgress(
                    id=row['id'],
                    episode_id=row['episode_id'],
                    timestamp=row['timestamp'],
                    last_watched=datetime.fromisoformat(row['last_watched']) if isinstance(row['last_watched'], str) else row['last_watched'],
                    completed=bool(row['completed'])
                ) for row in rows]

    async def mark_episode_watched(self, episode_id: int, watched: bool):
        async with aiosqlite.connect(self.db_path) as db:
            if watched:
                # Mark as completed (100% timestamp)
                await db.execute(
                    """INSERT INTO watch_progress (episode_id, timestamp, last_watched, completed)
                       SELECT id, duration, ?, 1 FROM episodes WHERE id = ?
                       ON CONFLICT(episode_id) DO UPDATE SET
                       timestamp = excluded.timestamp,
                       last_watched = excluded.last_watched,
                       completed = 1""",
                    (datetime.now(), episode_id)
                )
            else:
                # Remove progress or mark as 0
                await db.execute("DELETE FROM watch_progress WHERE episode_id = ?", (episode_id,))
            await db.commit()

    async def mark_series_watched(self, series_id: int, watched: bool):
        async with aiosqlite.connect(self.db_path) as db:
            if watched:
                # Mark all episodes as completed
                await db.execute(
                    """INSERT INTO watch_progress (episode_id, timestamp, last_watched, completed)
                       SELECT id, duration, ?, 1 FROM episodes WHERE series_id = ?
                       ON CONFLICT(episode_id) DO UPDATE SET
                       timestamp = excluded.timestamp,
                       last_watched = excluded.last_watched,
                       completed = 1""",
                    (datetime.now(), series_id)
                )
            else:
                # Clear all progress for this series
                await db.execute(
                    "DELETE FROM watch_progress WHERE episode_id IN (SELECT id FROM episodes WHERE series_id = ?)",
                    (series_id,)
                )
            await db.commit()
    # Online Progress Operations

    async def update_online_progress(self, progress: OnlineProgress):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO online_progress (show_id, show_name, episode_number, timestamp, thumbnail_url, local_path, completed, allmanga_id, nyaa_query)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(show_id, episode_number) DO UPDATE SET
                   timestamp = excluded.timestamp,
                   thumbnail_url = excluded.thumbnail_url,
                   local_path = excluded.local_path,
                   completed = excluded.completed,
                   allmanga_id = COALESCE(excluded.allmanga_id, online_progress.allmanga_id),
                   nyaa_query = COALESCE(excluded.nyaa_query, online_progress.nyaa_query)""",
                (progress.show_id, progress.show_name, progress.episode_number, progress.timestamp, 
                 progress.thumbnail_url, progress.local_path, int(progress.completed), progress.allmanga_id, progress.nyaa_query)
            )
            await db.commit()

    async def get_online_progress_for_show(self, show_id: str) -> List[OnlineProgress]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM online_progress WHERE show_id = ?", (show_id,)) as cursor:
                rows = await cursor.fetchall()
                return [OnlineProgress(
                    id=row['id'],
                    show_id=row['show_id'],
                    show_name=row['show_name'],
                    episode_number=int(row['episode_number']) if row['episode_number'] is not None else 0,
                    timestamp=float(row['timestamp']) if row['timestamp'] is not None else 0.0,
                    thumbnail_url=row['thumbnail_url'],
                    local_path=row['local_path'],
                    completed=bool(row['completed']),
                    last_watched=datetime.fromisoformat(row['last_watched']) if isinstance(row['last_watched'], str) else row['last_watched'],
                    allmanga_id=row['allmanga_id'] if 'allmanga_id' in row.keys() else None,
                    nyaa_query=row['nyaa_query'] if 'nyaa_query' in row.keys() else None
                ) for row in rows]

    async def get_recent_online_shows(self, limit: int = 20) -> List[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Get unique show_id/show_name pairs ordered by most recent last_watched
            # Using GROUP BY and MAX(last_watched)
            query = """
                SELECT show_id, show_name, thumbnail_url, MAX(allmanga_id) as allmanga_id, MAX(nyaa_query) as nyaa_query, MAX(last_watched) as latest
                FROM online_progress
                GROUP BY show_id
                ORDER BY latest DESC
                LIMIT ?
            """
            async with db.execute(query, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [{"show_id": r["show_id"], "show_name": r["show_name"], "thumbnail_url": r["thumbnail_url"], "allmanga_id": r["allmanga_id"], "nyaa_query": r["nyaa_query"]} for r in rows]
    async def get_downloaded_online_shows(self) -> List[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = """
                SELECT show_id, show_name, thumbnail_url, MAX(allmanga_id) as allmanga_id, MAX(nyaa_query) as nyaa_query
                FROM online_progress
                WHERE local_path IS NOT NULL AND local_path != ''
                GROUP BY show_id
                ORDER BY show_name ASC
            """
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                return [{"show_id": r["show_id"], "show_name": r["show_name"], "thumbnail_url": r["thumbnail_url"], "allmanga_id": r["allmanga_id"], "nyaa_query": r["nyaa_query"]} for r in rows]

    async def migrate_online_show(self, old_id: str, new_id: str, show_name: str, allmanga_id: str = None):
        """Migrates online progress entries from an old ID to a new canonical ID."""
        logger.info(f"Database: Migrating online progress {old_id} -> {new_id} ({show_name})")
        async with aiosqlite.connect(self.db_path) as db:
            # To avoid unique constraint conflicts, delete duplicates from old_id side
            await db.execute("""
                DELETE FROM online_progress 
                WHERE show_id = ? AND episode_number IN (
                    SELECT episode_number FROM online_progress WHERE show_id = ?
                )
            """, (old_id, new_id))
            
            # Update entries that match old_id
            if allmanga_id:
                await db.execute(
                    "UPDATE online_progress SET show_id = ?, show_name = ?, allmanga_id = ? WHERE show_id = ?",
                    (new_id, show_name, allmanga_id, old_id)
                )
            else:
                await db.execute(
                    "UPDATE online_progress SET show_id = ?, show_name = ? WHERE show_id = ?",
                    (new_id, show_name, old_id)
                )
            
            # Also update any entries that match the show_name but have a different ID
            # (Handles name-based IDs from previous versions)
            await db.execute("""
                DELETE FROM online_progress 
                WHERE show_name = ? AND show_id != ? AND episode_number IN (
                    SELECT episode_number FROM online_progress WHERE show_id = ?
                )
            """, (show_name, new_id, new_id))
            
            if allmanga_id:
                await db.execute(
                    "UPDATE online_progress SET show_id = ?, allmanga_id = ? WHERE show_name = ? AND show_id != ?",
                    (new_id, allmanga_id, show_name, new_id)
                )
            else:
                await db.execute(
                    "UPDATE online_progress SET show_id = ? WHERE show_name = ? AND show_id != ?",
                    (new_id, show_name, new_id)
                )
            await db.commit()

    # Download Task Operations

    async def update_download_task(self, task: DownloadTaskState):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO download_tasks (filename, url, status, progress, speed, eta, elapsed, referrer, metadata_json, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(filename) DO UPDATE SET
                   status = excluded.status,
                   progress = excluded.progress,
                   speed = excluded.speed,
                   eta = excluded.eta,
                   elapsed = excluded.elapsed,
                   last_updated = excluded.last_updated""",
                (task.filename, task.url, task.status, task.progress, task.speed, task.eta, task.elapsed, task.referrer, task.metadata_json, datetime.now())
            )
            await db.commit()

    async def get_all_download_tasks(self) -> List[DownloadTaskState]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM download_tasks ORDER BY last_updated DESC") as cursor:
                rows = await cursor.fetchall()
                return [DownloadTaskState(
                    id=row['id'],
                    filename=row['filename'],
                    url=row['url'],
                    status=row['status'],
                    progress=row['progress'],
                    speed=row['speed'],
                    eta=row['eta'],
                    elapsed=row['elapsed'],
                    referrer=row['referrer'],
                    metadata_json=row['metadata_json'],
                    last_updated=datetime.fromisoformat(row['last_updated']) if isinstance(row['last_updated'], str) else row['last_updated']
                ) for row in rows]

    async def remove_download_task(self, filename: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM download_tasks WHERE filename = ?", (filename,))
            await db.commit()

    async def clear_download_history(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM download_tasks WHERE status IN ('Finished', 'Failed', 'Cancelled')")
            await db.commit()

    # Planner Operations

    async def add_planner_entry(self, entry: PlannerEntry) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO planner (show_id, show_name, status, notes) VALUES (?, ?, ?, ?)",
                (entry.show_id, entry.show_name, entry.status, entry.notes)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_all_planner_entries(self) -> List[PlannerEntry]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM planner ORDER BY date_added DESC") as cursor:
                rows = await cursor.fetchall()
                return [PlannerEntry(
                    id=row['id'],
                    show_id=row['show_id'],
                    show_name=row['show_name'],
                    status=row['status'],
                    notes=row['notes'],
                    date_added=datetime.fromisoformat(row['date_added']) if isinstance(row['date_added'], str) else row['date_added']
                ) for row in rows]

    async def update_planner_entry(self, entry: PlannerEntry):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE planner SET show_id = ?, show_name = ?, status = ?, notes = ? WHERE id = ?",
                (entry.show_id, entry.show_name, entry.status, entry.notes, entry.id)
            )
            await db.commit()

    async def remove_planner_entry(self, entry_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM planner WHERE id = ?", (entry_id,))
            await db.commit()
