@echo off
title AniPlay Web Server
echo Starting AniPlay Web Server on http://localhost:8000 ...
uv run python -m uvicorn aniplay.api.server:app --host 0.0.0.0 --port 8000 --reload
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Server failed to start.
    pause
)
