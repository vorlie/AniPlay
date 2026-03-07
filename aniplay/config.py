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
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
# === .env example ===
# DEFAULT_LIBRARY_PATH=
# IMAGE_HOSTER=imgur
# === Copyparty credentials for Discord RPC thumbnails
# COPYPARTY_URL=
# COPYPARTY_USER=
# COPYPARTY_PWD=
# IMGUR_CLIENT_ID=
# === Media Preferences (comma-separated codes like jpn,eng,pol)
# PREFERRED_AUDIO=jpn
# PREFERRED_SUBTITLE=eng


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
PREFERRED_AUDIO = os.getenv("PREFERRED_AUDIO", "jpn")
PREFERRED_SUBTITLE = os.getenv("PREFERRED_SUBTITLE", "pol")

# UI Settings
PREFERRED_PLAYER = "embedded_vlc"  # "mpv", "vlc", or "embedded_vlc"
THUMBNAIL_CACHE_DIR = BASE_DIR / "cache" / "thumbnails"
DOWNLOADS_PATH = BASE_DIR / "downloads"
os.makedirs(THUMBNAIL_CACHE_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_PATH, exist_ok=True)

# Discord Rich Presence Settings
IMAGE_HOSTER = os.getenv("IMAGE_HOSTER", "copyparty") # "copyparty" or "imgur"
COPYPARTY_URL = os.getenv("COPYPARTY_URL", "URLHERE")
COPYPARTY_USER = os.getenv("COPYPARTY_USER", "USERNAMEHERE")
COPYPARTY_PWD = os.getenv("COPYPARTY_PWD", "PASSWORDHERE")
IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID", "")