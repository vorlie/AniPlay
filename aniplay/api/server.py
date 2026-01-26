import os
from fastapi import FastAPI, HTTPException, Header, Request, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Optional
import mimetypes
import aiofiles
import subprocess
#import json
#import shlex
import logging
import asyncio
import sys

# Windows-specific fix for asyncio subprocesses
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
#The function "set_event_loop_policy" is deprecated
#Deprecated since Python 3.14; will be removed in Python 3.16.

from ..database.db import DatabaseManager
from ..database.models import Series, Episode, WatchProgress, MediaTrack  # noqa: F401
from ..core.library_manager import LibraryManager
from ..utils.media_analyzer import MediaAnalyzer
from ..config import DB_PATH, WEB_DIR, DEFAULT_LIBRARY_PATH  # noqa: F401

app = FastAPI(title="AniPlay Web API")
logger = logging.getLogger("AniPlay.Web")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db = DatabaseManager(str(DB_PATH))
library = LibraryManager(db)

#The method "on_event" in class "FastAPI" is deprecated
#on_event is deprecated, use lifespan event handlers instead.
@app.on_event("startup")
async def startup():
    print("--- SERVER STARTING ---")
    print(f"Database: {DB_PATH}")
    print(f"Web Directory: {WEB_DIR}")
    if not WEB_DIR.exists():
        print(f"WARNING: Web directory not found at {WEB_DIR}")
    await db.initialize()

@app.get("/health")
async def health():
    return {"status": "ok", "web_dir": str(WEB_DIR), "exists": WEB_DIR.exists()}

# --- API Routes ---

@app.get("/api/series")
async def get_series():
    return await library.get_all_series()

@app.get("/api/series/{series_id}/episodes")
async def get_episodes(series_id: int):
    episodes = await library.get_episodes(series_id)
    # Fetch progress for each episode
    result = []
    for ep in episodes:
        progress = await db.get_progress(ep.id)
        ep_dict = ep.__dict__.copy()
        ep_dict["progress"] = progress.__dict__ if progress else None
        result.append(ep_dict)
    return result

@app.post("/api/progress")
async def update_progress(progress_data: dict):
    episode_id = progress_data.get("episode_id")
    timestamp = progress_data.get("timestamp")
    duration = progress_data.get("duration")
    
    if not episode_id:
        raise HTTPException(status_code=400, detail="Missing episode_id")
        
    completed = False
    if duration and duration > 0:
        completed = (timestamp / duration) >= 0.9
        
    progress = WatchProgress(
        episode_id=episode_id,
        timestamp=timestamp,
        completed=completed
    )
    await db.update_progress(progress)
    return {"status": "success"}

@app.get("/api/episodes/{episode_id}/tracks")
async def get_tracks(episode_id: int):
    # Find episode
    all_series = await library.get_all_series()
    episode = None
    for s in all_series:
        eps = await library.get_episodes(s.id)
        for e in eps:
            if e.id == episode_id:
                episode = e
                break
        if episode: 
            break

    if not episode or not os.path.exists(episode.path):
        raise HTTPException(status_code=404, detail="Episode not found")

    # 1. Try to get tracks from DB
    db_tracks = await db.get_tracks_for_episode(episode_id)
    
    # 2. Fallback: Probe if missing or duration is 0
    if not db_tracks or episode.duration <= 0:
        analyzer = MediaAnalyzer()
        metadata = analyzer.probe_file(episode.path)
        if metadata:
            # Sync to DB
            await db.update_episode_duration(episode_id, metadata.duration)
            await db.clear_episode_tracks(episode_id)
            for t in metadata.tracks:
                await db.add_media_track(MediaTrack(
                    episode_id=episode_id,
                    index=t.index,
                    type=t.type,
                    codec=t.codec,
                    language=t.language,
                    title=t.title,
                    sub_index=t.sub_index
                ))
            
            # Re-fetch for return
            db_tracks = await db.get_tracks_for_episode(episode_id)
            episode.duration = metadata.duration

    # 3. Format for API
    streams = []
    for t in db_tracks:
        streams.append({
            "index": t.index,
            "type": t.type,
            "codec": t.codec,
            "language": t.language,
            "title": t.title,
            "sub_index": t.sub_index
        })

    return {"tracks": streams, "duration": episode.duration}

@app.get("/api/posters")
async def get_poster(path: str):
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return FileResponse(path)

# Video Streaming with Range Support

def get_range_header(range_header: str, file_size: int):
    range_str = range_header.replace("bytes=", "")
    start_str, end_str = range_str.split("-")
    start = int(start_str)
    end = int(end_str) if end_str else file_size - 1
    return start, end

@app.get("/api/stream/{episode_id}")
async def stream_video(episode_id: int, request: Request, range: Optional[str] = Header(None)):
    # Find episode path
    # probably should optimize this later
    all_series = await library.get_all_series()
    episode = None
    for s in all_series:
        eps = await library.get_episodes(s.id)
        for e in eps:
            if e.id == episode_id:
                episode = e
                break
        if episode: 
            break
        
    if not episode or not os.path.exists(episode.path):
        raise HTTPException(status_code=404, detail="Video not found")

    video_path = Path(episode.path)
    file_size = video_path.stat().st_size
    content_type, _ = mimetypes.guess_type(video_path)
    if not content_type:
        content_type = "video/mp4"

    if range:
        start, end = get_range_header(range, file_size)
    else:
        start, end = 0, file_size - 1

    chunk_size = 1024 * 1024 # 1MB chunks
    
    async def range_stream(file_path, start, end, chunk_size):
        async with aiofiles.open(file_path, mode="rb") as f:
            await f.seek(start)
            bytes_left = (end - start) + 1
            while bytes_left > 0:
                to_read = min(chunk_size, bytes_left)
                data = await f.read(to_read)
                if not data:
                    break
                bytes_left -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str((end - start) + 1),
        "Content-Type": content_type,
    }
    
    return StreamingResponse(
        range_stream(video_path, start, end, chunk_size),
        headers=headers,
        status_code=206
    )

@app.get("/api/transcode/{episode_id}")
async def stream_transcoded(
    episode_id: int, 
    audio_track: Optional[int] = None, 
    sub_track: Optional[int] = None,
    start_time: float = 0
):
    # Find episode
    all_series = await library.get_all_series()
    episode = None
    for s in all_series:
        eps = await library.get_episodes(s.id)
        for e in eps:
            if e.id == episode_id:
                episode = e
                break
        if episode: 
            break
        
    if not episode or not os.path.exists(episode.path):
        raise HTTPException(status_code=404, detail="Video not found")

    # Build FFmpeg command for fMP4
    # Using "Fast Seek" (-ss before -i) to ensure instant start even on network/WSL paths.
    # -copyts and -start_at_zero to keep the subtitles in sync.
    cmd = [
        "ffmpeg", 
        "-loglevel", "error",
        "-ss", str(float(start_time)),
        "-i", episode.path,
        "-copyts", 
        "-start_at_zero",
        "-nostdin",
        "-y"
    ]

    # Audio Selection
    if audio_track is not None:
        cmd.extend(["-map", f"0:{audio_track}"])
    else:
        cmd.extend(["-map", "0:a:0?"])

    # Video Selection
    cmd.extend(["-map", "0:v:0"])

    # Subtitles Selection (Burn-in)
    if sub_track is not None:
        # For UNC/WSL paths, FFmpeg's subtitle filter is very picky.
        path_fixed = episode.path.replace("\\", "/")
        # Special escape for FFmpeg filter string: colon must be escaped
        path_esc = path_fixed.replace(":", "\\:").replace("'", "'\\\\''")
        cmd.extend(["-vf", f"subtitles='{path_esc}':si={sub_track}"])
    
    # Transcoding settings for fMP4
    cmd.extend([
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "frag_keyframe+empty_moov+default_base_moof",
        "-f", "mp4",
        "pipe:1"
    ])

    print(f"DEBUG: Running FFmpeg: {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, # Capture for debugging
        bufsize=10**6
    )

    def ffmpeg_stream():
        try:
            while True:
                data = process.stdout.read(65536)
                if not data:
                    # If we got no data, check if FFmpeg errored out
                    if process.poll() is not None:
                        err = process.stderr.read().decode('utf-8', errors='ignore')
                        if err:
                            print(f"FFmpeg Error Output:\n{err}")
                    break
                yield data
        finally:
            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=0.5)
                except:  # noqa: E722
                    try:
                        process.kill()
                    except:  # noqa: E722
                        pass
            try:
                process.stdout.close()
                process.stderr.close()
            except:  # noqa: E722
                pass

    return StreamingResponse(
        ffmpeg_stream(),
        media_type="video/mp4",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Accept-Ranges": "none" # Tell browser seek is handled by us
        }
    )

# Serve Frontend
if WEB_DIR.exists():
    @app.get("/")
    async def read_index():
        return FileResponse(WEB_DIR / "index.html")
        
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
else:
    @app.get("/")
    async def root_error():
        return {"error": f"Frontend directory not found at {WEB_DIR}"}
