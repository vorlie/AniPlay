import os
import logging
from pathlib import Path
from typing import Optional, List, Callable
from ..database.db import DatabaseManager
from ..database.models import Series, Episode, MediaTrack
from ..utils.file_scanner import FileScanner
from ..utils.media_analyzer import MediaAnalyzer
from ..config import DEFAULT_LIBRARY_PATH
from ..utils.logger import get_logger

logger = get_logger(__name__)

class LibraryManager:
    def __init__(self, db_manager: DatabaseManager):
        self._db = db_manager
        self._scanner = FileScanner()
        self._analyzer = MediaAnalyzer()

    async def scan_library(self, library_path: str = DEFAULT_LIBRARY_PATH, 
                           progress_callback: Optional[Callable[[str], None]] = None,
                           full_scan: bool = False):
        """
        Scan the library path and sync with database.
        If full_scan is False, existing metadata (titles, etc) are preserved.
        """
        logger.info(f"Starting library scan: {library_path} (Full Scan: {full_scan})")
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
            
            # 3. Update poster if missing or in full scan
            existing_series = await self._db.get_series(series_id)
            if poster_path and existing_series:
                should_update_poster = full_scan or not existing_series.thumbnail_path or not os.path.exists(existing_series.thumbnail_path)
                if should_update_poster:
                    await self._db.update_series_poster(series_id, poster_path)
            
            # 4. Scan episodes in folder
            ep_data_list = self._scanner.scan_series_folder(str(folder))
            logger.info(f"  Found {len(ep_data_list)} media files in {folder.name}")
            
            # 5. Process episodes
            series_total_size = 0
            for data in ep_data_list:
                # Calculate file size
                file_size = os.path.getsize(data["path"]) if os.path.exists(data["path"]) else 0
                series_total_size += file_size

                # Check if episode exists
                episode = Episode(
                    series_id=series_id,
                    filename=data["filename"],
                    path=data["path"],
                    episode_number=data["episode_number"],
                    season_number=data["season_number"],
                    folder_name=data["folder_name"],
                    size_bytes=file_size
                )
                
                # add_episode returns existing or new ID
                ep_id = await self._db.add_episode(episode)
                
                # Get possibly existing episode for comparison
                existing_ep = await self._db.get_episode_by_id(ep_id)
                
                if full_scan:
                    # Full scan: overwrite everything
                    await self._db.update_episode_metadata(episode)
                    await self._db.update_episode_size(ep_id, file_size)
                else:
                    if existing_ep:
                        if not existing_ep.title:
                            await self._db.update_episode_metadata(episode)
                        if existing_ep.size_bytes <= 0:
                            await self._db.update_episode_size(ep_id, file_size)

                # 6. Deep Metadata Scan (if needed)
                existing_tracks = await self._db.get_tracks_for_episode(ep_id)
                
                # Reload existing_ep to get updated duration if it was just added
                existing_ep = await self._db.get_episode_by_id(ep_id)
                
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

            # Update total series size after processing all episodes
            await self._db.update_series_size(series_id, series_total_size)

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
