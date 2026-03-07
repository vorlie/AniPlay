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

import json
import logging
import subprocess
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ..utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class TrackInfo:
    index: int
    type: str # 'audio', 'subtitle', 'video'
    codec: str
    language: str
    title: str
    sub_index: Optional[int] = None

@dataclass
class MediaMetadata:
    duration: float
    tracks: List[TrackInfo]

class MediaAnalyzer:
    @staticmethod
    def probe_file(file_path: str) -> Optional[MediaMetadata]:
        """Use ffprobe to extract tracks and duration from a media file."""
        logger.debug(f"Probing file: {file_path}")
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json", 
            "-show_streams", "-show_format", file_path
        ]
        
        try:
            # Force UTF-8 encoding for Windows/WSL compatibility
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            if result.returncode != 0:
                logger.error(f"Error probing {file_path}: {result.stderr}")
                return None
                
            data = json.loads(result.stdout)
            
            duration = float(data.get("format", {}).get("duration", 0))
            tracks = []
            sub_count = 0
            
            for s in data.get("streams", []):
                codec_type = s.get("codec_type")
                if codec_type not in ["audio", "subtitle", "video"]:
                    continue
                    
                lang = s.get("tags", {}).get("language", "und")
                title = s.get("tags", {}).get("title", f"{codec_type.capitalize()} {s.get('index')}")
                
                track = TrackInfo(
                    index=int(s.get("index", 0)),
                    type=codec_type,
                    codec=s.get("codec_name", ""),
                    language=lang,
                    title=title
                )
                
                if codec_type == "subtitle":
                    track.sub_index = sub_count
                    sub_count += 1
                    
                tracks.append(track)
            
            logger.debug(f"Found {len(tracks)} streams for {file_path}")
            return MediaMetadata(duration=duration, tracks=tracks)
            
        except Exception as e:
            logger.exception(f"Exception during ffprobe of {file_path}")
            return None
