import asyncio
import pytest
import os
from aniplay.database.db import DatabaseManager
from aniplay.database.models import Series, Episode, WatchProgress
from aniplay.config import BASE_DIR

import pytest_asyncio

@pytest_asyncio.fixture
async def db_manager():
    test_db = BASE_DIR / "test_aniplay.db"
    if test_db.exists():
        os.remove(test_db)
    
    manager = DatabaseManager(str(test_db))
    await manager.initialize()
    yield manager
    
    if test_db.exists():
        os.remove(test_db)

@pytest.mark.asyncio
async def test_series_operations(db_manager):
    series = Series(name="Test Anime", path="C:/Anime/Test")
    series_id = await db_manager.add_series(series)
    assert series_id > 0
    
    all_series = await db_manager.get_all_series()
    assert len(all_series) == 1
    assert all_series[0].name == "Test Anime"

@pytest.mark.asyncio
async def test_episode_operations(db_manager):
    series = Series(name="Test Anime", path="C:/Anime/Test")
    series_id = await db_manager.add_series(series)
    
    episode = Episode(series_id=series_id, filename="ep01.mkv", path="C:/Anime/Test/ep01.mkv", episode_number=1)
    ep_id = await db_manager.add_episode(episode)
    assert ep_id > 0
    
    episodes = await db_manager.get_episodes_for_series(series_id)
    assert len(episodes) == 1
    assert episodes[0].filename == "ep01.mkv"

@pytest.mark.asyncio
async def test_progress_operations(db_manager):
    series = Series(name="Test Anime", path="C:/Anime/Test")
    series_id = await db_manager.add_series(series)
    episode = Episode(series_id=series_id, filename="ep01.mkv", path="C:/Anime/Test/ep01.mkv")
    ep_id = await db_manager.add_episode(episode)
    
    progress = WatchProgress(episode_id=ep_id, timestamp=120.5, completed=False)
    await db_manager.update_progress(progress)
    
    saved_progress = await db_manager.get_progress(ep_id)
    assert saved_progress is not None
    assert saved_progress.timestamp == 120.5
    assert not saved_progress.completed
    
    # Update to completed
    progress.timestamp = 1500.0
    progress.completed = True
    await db_manager.update_progress(progress)
    
    updated_progress = await db_manager.get_progress(ep_id)
    assert updated_progress.completed is True
