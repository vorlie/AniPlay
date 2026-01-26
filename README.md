# AniPlay

AniPlay is a personal media server and player designed for anime libraries. It consists of a desktop application for local playback and a web server that allows streaming to other devices on a local network.

Note: The name "AniPlay" is purely functional and likely shared by dozens of other projects.

## Features

- **Dual Player Desktop App**: Local playback using either MPV or VLC.
- **Web Streaming**: FastAPI-based server with real-time FFmpeg transcoding (MKV to browser-compatible h264/AAC).
- **Subtitles & Audio**: Support for multiple audio tracks and burned-in subtitles in the browser.
- **Deep Metadata**: Automatic extraction of file duration and internal tracks using FFprobe, cached in a SQLite database.
- **Library Management**: Automatic folder-based scanning with support for seasons and extras.
- **Progress Sync**: Synchronization of watch progress between the desktop app and web clients.
- **Discord RPC**: Rich Presence integration for the desktop players.
- **Family Mode**: Toggleable progress syncing in the web client for shared environments.

## Requirements

- Python 3.14+
- FFmpeg and FFprobe (must be in system PATH)
- VLC Media Player (optional, for VLC desktop mode)
- MPV (optional, for MPV desktop mode)

## Installation

1. Install dependencies using uv:
   ```bash
   uv sync
   ```

2. Configure your library path in `aniplay/config.py`:
   ```python
   DEFAULT_LIBRARY_PATH = r"C:\Path\To\Your\Anime"
   ```

## Usage

### Desktop Application
Run the main application:
```bash
uv run python -m aniplay.main
```

### Web Server
Start the web API and client:
```bash
uv run python -m uvicorn aniplay.api.server:app --host 0.0.0.0 --port 8000
```
Access the player on other local devices via `http://[YOUR-PC-IP]:8000`.

## Project Structure

- `aniplay/api/`: FastAPI server implementation.
- `aniplay/web/`: Frontend assets (HTML, CSS, JS).
- `aniplay/core/`: Library indexing and management logic.
- `aniplay/database/`: SQLite schema and async database operations.
- `aniplay/ui/`: PyQt6 widgets for the desktop interface.
- `aniplay/utils/`: FFprobe media analysis and file system scanning.
- `aniplay/config.py`: Central configuration and path settings.
