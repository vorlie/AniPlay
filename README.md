Sure thing, Charlie. Here is the raw Markdown for you to copy and paste directly into your `README.md`.

# AniPlay

AniPlay is a personal media server and player designed for anime libraries. It provides a sleek, modern desktop interface to manage and play your local collection with high-fidelity players.

> **Note:** The name "AniPlay" is purely functional and likely shared by dozens of other projects.

## ✨ Features

* **Dual Player Engine**: Local playback using either **MPV** or **VLC** (fully configurable).
* **Tabbed Interface**: A seamless experience switching between your local library and settings.
* **Deep Metadata**: Automatic extraction of file duration and internal tracks using **FFprobe**, cached in a SQLite database.
* **Library Management**: Automatic folder-based scanning with support for seasons and extras.
* **Discord RPC**: Rich Presence integration to show what you're watching to your friends.
* **Custom Styling**: Premium dark theme with rounded corners and smooth micro-animations.

## 🛠 Requirements

* **Python 3.14+** (Strictly required)
* **FFmpeg & FFprobe** (Must be in system PATH)
* **VLC Media Player** (Recommended for the internal player component)
* **MPV** (Optional, for external player support)

> **Note:** While AniPlay includes an internal VLC component, having VLC installed system-wide is recommended for the best codec compatibility.

## 🚀 Installation

1.  **Sync Dependencies using `uv`**:
    ```bash
    uv sync
    ```

2.  **Configure Environment**:
    Copy the example environment file and set your library path:
    ```bash
    cp .env.example .env
    ```
    *Edit `.env` and set `DEFAULT_LIBRARY_PATH` to your anime folder.*

## 🐧 WSL / Linux Partitioned Drives

If your media library is stored on a Linux-partitioned drive (e.g., ext4), you must mount it using WSL before AniPlay can access the files.

1.  Find your drive: 
    ```powershell
    Get-CimInstance -Query "SELECT * FROM Win32_DiskDrive"
    ```
2.  Mount it (replace `PHYSICALDRIVE1` with your ID):
    ```bash
    wsl --mount \\.\PHYSICALDRIVE1 --partition 1 --type ext4
    ```

## 🖥 Usage

Run the main application using `uv`:
```bash
uv run python -m aniplay.main
```

---

## 📂 Project Structure

| Directory | Purpose |
| --- | --- |
| `aniplay/core/` | Library indexing and management logic. |
| `aniplay/database/` | SQLite schema and async database operations. |
| `aniplay/ui/` | PyQt6 widgets for the desktop interface. |
| `aniplay/utils/` | Media analysis, scrapers, and file system utilities. |
| `aniplay/config.py` | Central configuration and path settings. |
| `aniplay/main.py` | Application entry point. |
| `downloads/` | Default cache directory for processed streams. |

## 🛠 Troubleshooting

### 1. `FFmpeg` or `FFprobe` Not Found
If you see errors related to media analysis, ensure FFmpeg is installed and added to your system environment variables.
* **Windows:** `choco install ffmpeg` (or download from [ffmpeg.org](https://ffmpeg.org))
* **Linux:** `sudo apt install ffmpeg`
* **Check:** Run `ffmpeg -version` in your terminal to verify.

### 2. Python Version Mismatch
AniPlay strictly requires **Python 3.14+**. If your system default is older, `uv` can handle this for you:
```bash
uv python install 3.14
uv sync
```

### 3. VLC / MPV Errors

If the player fails to launch:

* **VLC:** Ensure you have the 64-bit version of VLC installed if you are running a 64-bit Python environment.
* **MPV:** If using the external MPV player, ensure the `mpv` executable is in your PATH.

### 4. Database Issues

If your library isn't updating or seems corrupted, you can safely delete `aniplay.db` and restart the app to trigger a fresh scan.

### 5. WSL Permission Denied

If you've mounted your drive but can't see files, ensure you are running the terminal as **Administrator** when performing the `wsl --mount` command.
