import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from ..database.db import DatabaseManager
from ..database.models import Series, Episode
from .file_scanner import FileScanner

logger = logging.getLogger(__name__)

class DatabaseMigrator:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.scanner = FileScanner()

    async def migrate_paths(self, library_path: str, dry_run: bool = True) -> Dict[str, Any]:
        """
        Migrate episode paths in the database to match the current filesystem structure.
        Handles moved files, reorganized season folders, and merged series.
        """
        stats = {
            "total_files_found": 0,
            "updated": [],
            "missing_in_physical": [],
            "not_moved": 0,
            "failed": [],
            "merged": 0
        }

        root = Path(library_path)
        if not root.exists():
            raise FileNotFoundError(f"Library path not found: {library_path}")

        # 1. Global Physical Scan
        # We scan the entire library to build a map of where files are NOW.
        all_physical_eps = []
        series_folders = [f for f in root.iterdir() if f.is_dir()]
        for folder in series_folders:
            all_physical_eps.extend(self.scanner.scan_series_folder(str(folder)))
        
        stats["total_files_found"] = len(all_physical_eps)
        
        # Map filename -> List[phys_ep_data]
        phys_filename_map = {}
        for pe in all_physical_eps:
            fname = pe["filename"]
            if fname not in phys_filename_map:
                phys_filename_map[fname] = []
            phys_filename_map[fname].append(pe)
            
        # Map physical series root -> series_id (from DB)
        all_series_in_db = await self.db.get_all_series()
        series_path_to_id = {str(Path(s.path)): s.id for s in all_series_in_db}

        # 2. Iterate DB Episodes
        # We check every episode record and try to see if its path matches reality.
        db_episodes = await self.db.get_all_episodes()
        
        for db_ep in db_episodes:
            # 2.1 Check if current path exists (quick path)
            current_path = Path(db_ep.path)
            
            # Find best physical match
            match = None
            if current_path.exists():
                # Still where it was, but let's see if metadata (season/folder) changed
                # (e.g. it was in root but now we consider it Season 1)
                match = next((pe for pe in all_physical_eps if pe["path"] == db_ep.path), None)
            
            if not match:
                # ORPHAN! The file moved. Try to find it by filename.
                potential_matches = phys_filename_map.get(db_ep.filename, [])
                
                if len(potential_matches) == 1:
                    # Unique filename in library! Highly likely it's the same file.
                    match = potential_matches[0]
                elif len(potential_matches) > 1:
                    # Multiple files with same name? Try to match by season/episode numbers.
                    match = next((pe for pe in potential_matches 
                                 if pe["season_number"] == db_ep.season_number 
                                 and pe["episode_number"] == db_ep.episode_number), None)
                    
                    # If still no match, try matching by parent folder name hint
                    if not match:
                        # Very defensive, but better than a wrong match
                        pass

            # 2.2 Process Match
            if match:
                new_path = match["path"]
                
                # Check if anything changed
                path_changed = new_path != db_ep.path
                metadata_changed = (match["season_number"] != db_ep.season_number or 
                                   match["folder_name"] != db_ep.folder_name)
                
                if path_changed or metadata_changed:
                    try:
                        # Determine if it moved to a DIFFERENT series (Merging)
                        rel_path = Path(new_path).relative_to(root)
                        new_series_root = root / rel_path.parts[0]
                        new_series_id = series_path_to_id.get(str(new_series_root))
                        
                        is_merge = new_series_id is not None and new_series_id != db_ep.series_id

                        if not dry_run:
                            # Update path and metadata
                            await self.db.update_episode_path(
                                db_ep.id, 
                                new_path, 
                                match["filename"], 
                                match["folder_name"], 
                                match["season_number"]
                            )
                            # Update parent series if merged
                            if is_merge:
                                await self.db.update_episode_series(db_ep.id, new_series_id)
                                stats["merged"] += 1
                        
                        stats["updated"].append({
                            "series_hint": rel_path.parts[0],
                            "old_path": db_ep.path,
                            "new_path": new_path,
                            "merged": is_merge
                        })
                    except Exception as e:
                        logger.error(f"Failed to migrate episode {db_ep.id}: {e}")
                        stats["failed"].append(db_ep.path)
                else:
                    stats["not_moved"] += 1
            else:
                stats["missing_in_physical"].append(db_ep.path)

        return stats
