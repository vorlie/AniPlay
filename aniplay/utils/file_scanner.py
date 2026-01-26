import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from ..config import VIDEO_EXTENSIONS

class FileScanner:
    # Regex patterns for episode parsing
    # 1. S01E01 / S1E1
    # 2. 01 (just a number)
    # 3. Episode 01
    # 4. - 01
    PATTERNS = [
        re.compile(r'[Ss](\d+)[Ee](\d+)'),              # S01E01
        re.compile(r' - (\d+)\b'),                      # - 01
        re.compile(r'[Ee]pisode\s*(\d+)'),              # Episode 01
        re.compile(r'\b(\d{1,3})\b'),                    # 01 (fallback)
    ]

    @staticmethod
    def parse_episode_info(filename: str) -> Dict[str, Optional[int]]:
        """Extract season and episode number from filename."""
        # Remove extension
        name = os.path.splitext(filename)[0]
        
        season = None
        episode = None

        # Try S01E01 pattern first as it's most specific
        match = FileScanner.PATTERNS[0].search(filename)
        if match:
            season = int(match.group(1))
            episode = int(match.group(2))
            return {"season": season, "episode": episode}

        # Try other patterns for episode number
        for i in range(1, len(FileScanner.PATTERNS)):
            match = FileScanner.PATTERNS[i].search(filename)
            if match:
                # If found multiple numbers in a generic pattern, it might be tricky
                # But usually the first one after Name - is the episode
                episode = int(match.group(1))
                break
        
        # Try to find season if it's in the path (e.g. "Season 1")
        # This will be handled in scan_directory
        
        return {"season": season, "episode": episode}

    @staticmethod
    def get_video_files(directory: str) -> List[Path]:
        """Get all video files in a directory (recursive)."""
        video_files = []
        path = Path(directory)
        
        if not path.exists():
            return []

        for ext in VIDEO_EXTENSIONS:
            video_files.extend(path.rglob(f"*{ext}"))
            video_files.extend(path.rglob(f"*{ext.upper()}"))
            
        return sorted(list(set(video_files)))

    @staticmethod
    def scan_series_folder(series_path: str) -> List[Dict[str, Any]]:
        """
        Scan a single series folder.
        Handles:
        - Series/Episode.mkv
        - Series/Season 1/Episode.mkv
        """
        episodes = []
        base_path = Path(series_path)
        
        for file_path in FileScanner.get_video_files(series_path):
            relative_path = file_path.relative_to(base_path)
            parts = relative_path.parts
            
            info = FileScanner.parse_episode_info(file_path.name)
            
            # If season not found in filename, check if it's in a "Season X" folder
            if info["season"] is None and len(parts) > 1:
                for part in parts:
                    season_match = re.search(r'[Ss]eason\s*(\d+)', part)
                    if season_match:
                        info["season"] = int(season_match.group(1))
                        break
            
            # Determine folder name (immediate subfolder or None)
            folder_name = parts[0] if len(parts) > 1 else None
            
            episodes.append({
                "filename": file_path.name,
                "path": str(file_path),
                "episode_number": info["episode"],
                "season_number": info["season"],
                "folder_name": folder_name
            })
            
        return episodes
