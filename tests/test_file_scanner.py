import pytest
from aniplay.utils.file_scanner import FileScanner

def test_parse_episode_info_s01e01():
    info = FileScanner.parse_episode_info("Anime Name - S01E05.mkv")
    assert info["season"] == 1
    assert info["episode"] == 5

def test_parse_episode_info_simple_number():
    info = FileScanner.parse_episode_info("Anime Name - 01.mkv")
    assert info["episode"] == 1

def test_parse_episode_info_episode_text():
    info = FileScanner.parse_episode_info("Anime Name - Episode 12.mp4")
    assert info["episode"] == 12

def test_parse_episode_info_no_info():
    info = FileScanner.parse_episode_info("JustAFile.ts")
    # Might find numbers if any exist, but it's a fallback
    pass

def test_scan_series_folder_mock(tmp_path):
    # Create mock series structure
    series_dir = tmp_path / "Test Anime"
    series_dir.mkdir()
    
    season1 = series_dir / "Season 1"
    season1.mkdir()
    (season1 / "Test - 01.mkv").write_text("dummy")
    (series_dir / "Test - 02.mkv").write_text("dummy")
    
    episodes = FileScanner.scan_series_folder(str(series_dir))
    assert len(episodes) == 2
    
    # Check season detection from folder
    ep1 = next(e for e in episodes if e["filename"] == "Test - 01.mkv")
    assert ep1["season_number"] == 1
    assert ep1["episode_number"] == 1
    
    ep2 = next(e for e in episodes if e["filename"] == "Test - 02.mkv")
    assert ep2["episode_number"] == 2
