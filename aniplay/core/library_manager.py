import os
import logging
from pathlib import Path
from typing import Optional, List, Callable
from ..database.db import DatabaseManager
from ..database.models import Series, Episode, MediaTrack
from ..utils.file_scanner import FileScanner
from ..utils.media_analyzer import MediaAnalyzer
from ..config import DEFAULT_LIBRARY_PATH

logger = logging.getLogger(__name__)

class LibraryManager:
    def __init__(self, db_manager: DatabaseManager):
        self._db = db_manager
        self._scanner = FileScanner()
        self._analyzer = MediaAnalyzer()

    async def scan_library(self, library_path: str = DEFAULT_LIBRARY_PATH, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Scan the entire library path and sync with database.
        Each folder in library_path is treated as a Series.
        """
        logger.info(f"Starting library scan: {library_path}")
        root = Path(library_path)
        if not root.exists():
            return

        # Get all top-level directories (Series)
        series_folders = [f for f in root.iterdir() if f.is_dir()]
        
        for folder in series_folders:
            logger.info(f"Scanning series: {folder.name}")
            if progress_callback:
                progress_callback(f"Scanning {folder.name}...")
            
            # 1. Detect Poster
            poster_path = self._find_poster(folder)
            
            # 2. Add/Get Series
            series = Series(name=folder.name, path=str(folder), thumbnail_path=poster_path)
            series_id = await self._db.add_series(series)
            
            # 3. If series exists, only update poster if it's currently missing or invalid
            existing = await self._db.get_series(series_id)
            if poster_path and existing and (not existing.thumbnail_path or not os.path.exists(existing.thumbnail_path)):
                await self._db.update_series_poster(series_id, poster_path)
            
            # 4. Scan episodes in folder
            ep_data_list = self._scanner.scan_series_folder(str(folder))
            logger.info(f"  Found {len(ep_data_list)} media files in {folder.name}")
            
            # 4. Add episodes to DB
            for data in ep_data_list:
                episode = Episode(
                    series_id=series_id,
                    filename=data["filename"],
                    path=data["path"],
                    episode_number=data["episode_number"],
                    season_number=data["season_number"],
                    folder_name=data["folder_name"]
                )
                ep_id = await self._db.add_episode(episode)
                # Always update metadata for existing episodes to ensure folder_name is set
                await self._db.update_episode_metadata(episode)

                # 5. Deep Metadata Scan (if needed)
                # Check if episode already has tracks or duration
                existing_ep = await self._db.get_episode_by_id(ep_id)
                existing_tracks = await self._db.get_tracks_for_episode(ep_id)
                
                if existing_ep and (existing_ep.duration <= 0 or not existing_tracks):
                    logger.info(f"    Probing Metadata: {episode.filename}")
                    if progress_callback:
                        progress_callback(f"  Probing {episode.filename}...")
                    
                    metadata = self._analyzer.probe_file(episode.path)
                    if metadata:
                        # Update Duration
                        await self._db.update_episode_duration(ep_id, metadata.duration)
                        
                        # Update Tracks
                        await self._db.clear_episode_tracks(ep_id)
                        for t in metadata.tracks:
                            track = MediaTrack(
                                episode_id=ep_id,
                                index=t.index,
                                type=t.type,
                                codec=t.codec,
                                language=t.language,
                                title=t.title,
                                sub_index=t.sub_index
                            )
                            await self._db.add_media_track(track)
                        logger.info(f"      Success: {len(metadata.tracks)} tracks found")

        logger.info("Library scan complete!")
        if progress_callback:
            progress_callback("Scan complete!")

    def _find_poster(self, folder_path: Path) -> Optional[str]:
        """Look for common poster filenames in the series folder."""
        common_names = [
            "folder.jpg", "folder.png", "poster.jpg", "poster.png", 
            "cover.jpg", "cover.png", "banner.jpg", "banner.png"
        ]
        
        # 1. Check direct matches
        for name in common_names:
            p = folder_path / name
            if p.exists():
                return str(p)
                
        # 2. Case-insensitive search
        try:
            for item in folder_path.iterdir():
                if item.is_file() and item.name.lower() in common_names:
                    return str(item)
        except Exception:
            pass
            
        return None

    async def get_all_series(self) -> List[Series]:
        return await self._db.get_all_series()

    async def get_episodes(self, series_id: int) -> List[Episode]:
        return await self._db.get_episodes_for_series(series_id)
