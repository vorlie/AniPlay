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
