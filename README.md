# AniPlay

AniPlay is a personal media server and player designed for anime libraries. It provides a sleek, modern desktop interface to manage and play your local collection with high-fidelity players.

Note: The name "AniPlay" is purely functional and likely shared by dozens of other projects.

## Features

- **Dual Player Engine**: Local playback using either **MPV** or **VLC** (fully configurable).
- **Tabbed Interface**: A seamless experience switching between your local library and settings.
- **Deep Metadata**: Automatic extraction of file duration and internal tracks using FFprobe, cached in a SQLite database.
- **Library Management**: Automatic folder-based scanning with support for seasons and extras.
- **Discord RPC**: Rich Presence integration to show what you're watching to your friends.
- **Custom Styling**: Premium dark theme with rounded corners and smooth micro-animations.

## Requirements

- Python 3.14+
- FFmpeg and FFprobe (must be in system PATH)
- VLC Media Player (optional, for VLC desktop mode)
- MPV (optional, for MPV desktop mode)

## WSL / Linux Partitioned Drives

If your media library is stored on a Linux-partitioned drive (e.g., ext4), you must mount it using WSL before AniPlay can access the files.

> "\\.\PHYSICALDRIVE1" might be different for you, use `Get-CimInstance -Query "SELECT * FROM Win32_DiskDrive"` to find the correct drive.
```bash
wsl --mount \\.\PHYSICALDRIVE1 --partition 1 --type ext4
```

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

## Project Structure

- `aniplay/core/`: Library indexing and management logic.
- `aniplay/database/`: SQLite schema and async database operations.
- `aniplay/ui/`: PyQt6 widgets for the desktop interface.
- `aniplay/utils/`: Media analysis, scrapers, and file system utilities.
- `aniplay/config.py`: Central configuration and path settings.
- `aniplay/main.py`: Application entry point.
- `downloads/`: Default cache directory for processed streams.
