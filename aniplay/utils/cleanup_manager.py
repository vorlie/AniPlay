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

import os
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class CleanupManager:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.junk_patterns = [
            "*-thumb.jpg",
            "*-thumb.jpeg",
            "*.nfo"
        ]

    def scan_for_junk(self, library_path: str) -> List[Path]:
        """Scan library for junk files based on patterns."""
        root = Path(library_path)
        junk_files = []
        
        # We only look for specific patterns to avoid deleting user custom posters
        # Common Jellyfin junk: -thumb.jpg, -thumb.jpeg, *.nfo
        for pattern in self.junk_patterns:
            junk_files.extend(root.rglob(pattern))
            
        return sorted(list(set(junk_files)))

    def cleanup(self, files: List[Path]) -> Dict[str, Any]:
        """Remove the specified files."""
        results = {
            "deleted": [],
            "failed": [],
            "total_size": 0
        }
        
        for file_path in files:
            try:
                size = file_path.stat().st_size
                if not self.dry_run:
                    file_path.unlink()
                
                results["deleted"].append(str(file_path))
                results["total_size"] += size
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
                results["failed"].append({"path": str(file_path), "error": str(e)})

        return results
