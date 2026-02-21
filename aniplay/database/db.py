import aiosqlite
#import sqlite3
from typing import List, Optional, Any  # noqa: F401
from datetime import datetime
from .models import Series, Episode, WatchProgress, MediaTrack
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
            
            # Migrations
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
