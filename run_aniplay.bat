@echo off
title AniPlay 
echo Starting AniPlay...
uv run python -m aniplay.main
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application crashed or failed to start.
    pause
)
