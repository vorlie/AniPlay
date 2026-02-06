import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base Paths
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "aniplay.db"
WEB_DIR = BASE_DIR / "aniplay" / "web"

# Library Settings
DEFAULT_LIBRARY_PATH = os.getenv("DEFAULT_LIBRARY_PATH", "PATHHERE")

# Supported Formats (MPV supports almost everything, but these are for scanning)
VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".webm", ".flv", ".m4v", ".ts", ".mov", ".wmv", ".mpg", ".mpeg"
}

# Playback Settings
AUTO_SAVE_INTERVAL = 5  # seconds
COMPLETE_THRESHOLD = 0.9  # 90% watched marks as completed

# UI Settings
PREFERRED_PLAYER = "embedded_vlc"  # "mpv", "vlc", or "embedded_vlc"
THUMBNAIL_CACHE_DIR = BASE_DIR / "cache" / "thumbnails"
os.makedirs(THUMBNAIL_CACHE_DIR, exist_ok=True)

# Discord Rich Presence Settings
COPYPARTY_URL = os.getenv("COPYPARTY_URL", "URLHERE")
COPYPARTY_USER = os.getenv("COPYPARTY_USER", "USERNAMEHERE")
COPYPARTY_PWD = os.getenv("COPYPARTY_PWD", "PASSWORDHERE")
