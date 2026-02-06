import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from .file_scanner import FileScanner
from ..config import VIDEO_EXTENSIONS

class OrgAnalyzer:
    def __init__(self):
        self.scanner = FileScanner()

    def analyze_series(self, series_path: str) -> Dict[str, Any]:
        """
        Analyze a series folder for organization issues.
        Returns a dictionary with issues found.
        """
        base_path = Path(series_path)
        issues = []
        
        # 1. Get all video files
        all_videos = self.scanner.get_video_files(series_path)
        if not all_videos:
            return {"status": "empty", "issues": []}

        # 2. Check for loose files vs folders
        root_videos = [v for v in all_videos if v.parent == base_path]
        subfolder_videos = [v for v in all_videos if v.parent != base_path]
        
        subfolders = [f for f in base_path.iterdir() if f.is_dir()]
        media_subfolders = []
        for sf in subfolders:
            if any(v.is_relative_to(sf) for v in subfolder_videos):
                media_subfolders.append(sf)

        if root_videos and media_subfolders:
            issues.append({
                "type": "mixed_content",
                "message": f"Found {len(root_videos)} videos in root and {len(media_subfolders)} subfolders containing media.",
                "files": [v.name for v in root_videos[:3]]
            })

        # 3. Check subfolder names
        for sf in media_subfolders:
            # Standard: "Season X" or "Specials"
            if not re.match(r'^([Ss]eason\s*\d+|[Ss]pecials)$', sf.name):
                issues.append({
                    "type": "non_standard_folder",
                    "message": f"Subfolder '{sf.name}' does not follow 'Season X' or 'Specials' naming convention.",
                    "folder": sf.name
                })

        # 4. Check for multiple seasons without season folders
        seasons_found = set()
        for video in all_videos:
            info = self.scanner.parse_episode_info(video.name)
            if info["season"] is not None:
                seasons_found.add(info["season"])
        
        if len(seasons_found) > 1 and not media_subfolders:
            issues.append({
                "type": "missing_season_folders",
                "message": f"Multiple seasons ({sorted(list(seasons_found))}) detected but no season folders used.",
                "seasons": sorted(list(seasons_found))
            })
        elif len(seasons_found) == 1 and not media_subfolders and root_videos:
            season = list(seasons_found)[0]
            issues.append({
                "type": "missing_season_folder",
                "message": f"Single season ({season}) detected but no 'Season {season}' folder used (episodes in root).",
                "season": season
            })

        # 5. Check for inconsistent seasons in a folder
        folder_to_seasons = {}
        for video in all_videos:
            rel_folder = video.parent.relative_to(base_path)
            info = self.scanner.parse_episode_info(video.name)
            if info["season"] is not None:
                if str(rel_folder) not in folder_to_seasons:
                    folder_to_seasons[str(rel_folder)] = set()
                folder_to_seasons[str(rel_folder)].add(info["season"])
        
        for folder, seasons in folder_to_seasons.items():
            if len(seasons) > 1:
                issues.append({
                    "type": "inconsistent_seasons",
                    "message": f"Folder '{folder}' contains episodes from multiple seasons: {sorted(list(seasons))}.",
                    "folder": folder,
                    "seasons": sorted(list(seasons))
                })

        return {
            "status": "issues" if issues else "ok",
            "issues": issues,
            "total_videos": len(all_videos),
            "root_videos": len(root_videos),
            "media_folders": [sf.name for sf in media_subfolders]
        }
