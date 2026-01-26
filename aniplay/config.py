import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "aniplay.db"
WEB_DIR = BASE_DIR / "aniplay" / "web"

# Library Settings
DEFAULT_LIBRARY_PATH = r"PATH TO YOUR LIBRARY"

# Supported Formats (MPV supports almost everything, but these are for scanning)
VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".webm", ".flv", ".m4v", ".ts", ".mov", ".wmv", ".mpg", ".mpeg"
}

# Playback Settings
AUTO_SAVE_INTERVAL = 5  # seconds
COMPLETE_THRESHOLD = 0.9  # 90% watched marks as completed

# UI Settings
PREFERRED_PLAYER = "vlc" # "mpv" or "vlc"
THUMBNAIL_CACHE_DIR = BASE_DIR / "cache" / "thumbnails"
os.makedirs(THUMBNAIL_CACHE_DIR, exist_ok=True)
