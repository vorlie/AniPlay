from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class Series:
    name: str
    path: str
    id: Optional[int] = None
    thumbnail_path: Optional[str] = None
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
    duration: float = 0.0
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
