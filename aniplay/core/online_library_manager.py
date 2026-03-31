import os
import re
import hashlib
import shutil
import asyncio
from typing import List, Dict, Any, Optional
from ..utils.logger import get_logger

logger = get_logger(__name__)

class OnlineLibraryManager:
    """
    Manages the online download library, handling folder organization and migration.
    """
    def __init__(self, download_dir: str, db_manager: Any):
        self.download_dir = download_dir
        self.db_manager = db_manager

    def get_nyaa_folder_name(self, series_name: str, show_id: str) -> str:
        """Returns the canonical folder name: nyaa-hash."""
        return show_id

    def get_allanime_folder_name(self, show_id: str) -> str:
        """Returns the canonical folder name for AllAnime: allanime-hash."""
        # Use a stable hash of the original AllAnime ID
        name_hash = hashlib.md5(show_id.encode('utf-8')).hexdigest()[:12]
        return f"allanime-{name_hash}"

    def _clean_name(self, title: str) -> str:
        """Helper to get series name from torrent title."""
        # Strip [tags] and (brackets)
        cleaned = re.sub(r'\[.*?\]|\(.*?\)', '', title).strip()
        # Also strip common resolution/version strings that might not be in brackets
        cleaned = re.sub(r'(?i)\d{3,4}p|x264|x265|hevc|web-dl|bluray', '', cleaned).strip()
        # Strip episode numbers like " - 01" or " 01" at the end
        cleaned = re.sub(r'\s+-\s+\d+.*$', '', cleaned).strip()
        cleaned = re.sub(r'\s+\d+(?:\s|$).*$', '', cleaned).strip()
        return cleaned if cleaned else title

    async def migrate_downloads(self):
        """
        Scans the download directory and migrates Nyaa and AllAnime folders to the new format.
        """
        logger.info(f"Starting library migration in {self.download_dir}...")
        
        if not os.path.exists(self.download_dir):
            return

        migrated_count = 0
        all_folders = os.listdir(self.download_dir)
        
        # We need a list of known show IDs to help identify folders
        known_shows = {} # folder_name -> {show_id, show_name, is_nyaa}
        async with self.db_manager.get_db_connection() as db:
            db.row_factory = aiosqlite.Row
            # We assume show_id is the folder name for old style
            cursor = await db.execute("SELECT DISTINCT show_id, show_name FROM online_progress")
            rows = await cursor.fetchall()
            for r in rows:
                known_shows[r['show_id']] = {
                    "show_id": r['show_id'],
                    "show_name": r['show_name'],
                    "is_nyaa": r['show_id'].startswith('nyaa-')
                }

        for folder_name in all_folders:
            folder_path = os.path.normpath(os.path.join(self.download_dir, folder_name))
            if not os.path.isdir(folder_path):
                continue
                
            # Identification:
            new_folder_name = None
            show_id = None
            series_name = None
            
            # Skip folders that are already Nyaa in new format
            if folder_name.startswith("nyaa-") and len(folder_name) == 17:
                # We want to upgrade them to 'Title [nyaa-hash]' if possible
                show_id = folder_name
                # Find series name from DB or files
                info = known_shows.get(show_id)
                series_name = info['show_name'] if info else None
                if not series_name:
                    series_name = self._get_series_name_from_files(folder_path)
                
                if series_name:
                    new_folder_name = self.get_nyaa_folder_name(series_name, show_id)
            
            # Skip/Handle AllAnime new format
            elif folder_name.startswith("allanime-") and len(folder_name) == 21: # allanime- + 12 chars
                continue

            # Handle Nyaa flexible format (already correct)
            elif re.search(r'\[nyaa-[a-f0-9]{12}\]$', folder_name):
                continue
            
            # Identify other folders
            if not new_folder_name:
                info = known_shows.get(folder_name)
                if info:
                    show_id = info['show_id']
                    series_name = info['show_name']
                    # Is it Nyaa or AllAnime?
                    if show_id.startswith('nyaa-'):
                        new_folder_name = self.get_nyaa_folder_name(series_name, show_id)
                    else:
                        # AllAnime (or other)
                        new_folder_name = self.get_allanime_folder_name(show_id)
                else:
                    # Not in DB by name, try to guess
                    if re.match(r'^[a-fA-F0-9]{40}$', folder_name): # Hash
                        # It's likely an old Nyaa torrent hash
                        series_name = self._get_series_name_from_files(folder_path)
                        if series_name:
                            name_hash = hashlib.md5(series_name.encode('utf-8')).hexdigest()[:12]
                            show_id = f"nyaa-{name_hash}"
                            new_folder_name = self.get_nyaa_folder_name(series_name, show_id)
            
            if not new_folder_name:
                continue

            new_folder_path = os.path.normpath(os.path.join(self.download_dir, new_folder_name))
            if folder_path.lower() == new_folder_path.lower():
                continue

            logger.info(f"Migrating {folder_name} -> {new_folder_name}")
            
            try:
                # Move contents
                if not os.path.exists(new_folder_path):
                    os.makedirs(new_folder_path, exist_ok=True)
                
                for f in os.listdir(folder_path):
                    src = os.path.join(folder_path, f)
                    dst = os.path.join(new_folder_path, f)
                    if not os.path.exists(dst):
                        shutil.move(src, dst)
                
                # Update database
                if show_id and hasattr(self.db_manager, "migrate_online_show"):
                    await self.db_manager.migrate_online_show(folder_name, show_id, series_name or folder_name)
                
                # Cleanup old folder
                if not os.listdir(folder_path):
                    os.rmdir(folder_path)
                
                migrated_count += 1
            except Exception as e:
                logger.error(f"Failed to migrate {folder_name}: {e}")

        logger.info(f"Migration complete. Migrated {migrated_count} folders.")
        return migrated_count

    def _get_series_name_from_files(self, folder_path: str) -> Optional[str]:
        video_file = None
        max_size = 0
        for root, dirs, files in os.walk(folder_path):
            for f in files:
                if f.lower().endswith(('.mkv', '.mp4', '.avi', '.mov')):
                    f_size = os.path.getsize(os.path.join(root, f))
                    if f_size > max_size:
                        max_size = f_size
                        video_file = f
        return self._clean_name(video_file) if video_file else None
