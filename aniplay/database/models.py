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

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class Series:
    name: str
    path: str
    id: Optional[int] = None
    thumbnail_path: Optional[str] = None
    rpc_image_url: Optional[str] = None
    size_bytes: int = 0
    date_added: datetime = field(default_factory=datetime.now)

@dataclass
class MediaTrack:
    episode_id: int
    index: int
    type: str  # 'audio', 'subtitle', 'video'
    codec: str
    language: str
    title: str
    sub_index: Optional[int] = None
    id: Optional[int] = None

@dataclass
class Episode:
    series_id: int
    filename: str
    path: str
    id: Optional[int] = None
    title: Optional[str] = None
    duration: float = 0.0
    size_bytes: int = 0
    date_added: datetime = field(default_factory=datetime.now)
    episode_number: Optional[int] = None
    season_number: Optional[int] = None
    folder_name: Optional[str] = None
    tracks: List[MediaTrack] = field(default_factory=list)

@dataclass
class WatchProgress:
    episode_id: int
    timestamp: float = 0.0
    last_watched: datetime = field(default_factory=datetime.now)
    completed: bool = False
    id: Optional[int] = None

@dataclass
class OnlineProgress:
    show_id: str
    show_name: str
    episode_number: int
    timestamp: float = 0.0
    thumbnail_url: Optional[str] = None
    local_path: Optional[str] = None
    completed: bool = False
    last_watched: datetime = field(default_factory=datetime.now)
    allmanga_id: Optional[str] = None
    nyaa_query: Optional[str] = None
    id: Optional[int] = None

@dataclass
class DownloadTaskState:
    filename: str
    url: str
    status: str
    progress: float = 0.0
    speed: str = "0.0x"
    eta: str = ""
    elapsed: str = ""
    referrer: Optional[str] = None
    metadata_json: str = "{}"
    last_updated: datetime = field(default_factory=datetime.now)
    id: Optional[int] = None

@dataclass
class PlannerEntry:
    show_name: str
    id: Optional[int] = None
    show_id: Optional[str] = None
    status: str = "Plan to Watch"
    notes: str = ""
    date_added: datetime = field(default_factory=datetime.now)
    # AniList enrichment fields (optional, non-breaking)
    anilist_id: Optional[int] = None
    cover_url: Optional[str] = None
    episodes: Optional[int] = None
    average_score: Optional[float] = None
    next_episode: Optional[int] = None
    next_episode_airing: Optional[int] = None
    last_synced: Optional[datetime] = None
    # Optional display fields persisted from AniList
    display_title: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    description: Optional[str] = None
