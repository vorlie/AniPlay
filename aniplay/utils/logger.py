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

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

def setup_logging(level=logging.INFO, log_to_file=True):
    """
    Sets up a centralized logging system for AniPlay.
    Logs to console and optionally to a file with rotation on launch.
    """
    log_file = Path("aniplay.log")
    logs_dir = Path("logs")
    
    if log_to_file:
        # Create logs directory if it doesn't exist
        logs_dir.mkdir(exist_ok=True)
        
        # Rotate existing log file if it exists
        if log_file.exists():
            timestamp = datetime.fromtimestamp(log_file.stat().st_mtime).strftime("%Y%m%d_%H%M%S")
            rotated_log = logs_dir / f"aniplay_{timestamp}.log"
            try:
                # Use shutil.move for safer rotation across filesystems if needed
                import shutil
                shutil.move(str(log_file), str(rotated_log))
            except Exception as e:
                print(f"Failed to rotate log: {e}")

        # Cleanup old logs (keep last 10)
        try:
            log_files = sorted(logs_dir.glob("aniplay_*.log"), key=os.path.getmtime, reverse=True)
            for old_log in log_files[10:]:
                old_log.unlink()
        except Exception as e:
            print(f"Failed to cleanup old logs: {e}")

    # Define formatting
    log_format = '%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d) - %(message)s'
    formatter = logging.Formatter(log_format)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers to avoid duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler
    if log_to_file:
        # Always log to the main aniplay.log for current session
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Silence noisy third-party loggers
    logging.getLogger("aiosqlite").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.INFO)
    logging.getLogger("qasync").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("charset_normalizer").setLevel(logging.WARNING)

    logging.info(f"Logging initialized. Level: {logging.getLevelName(level)}, Current File: {log_file}")

def get_logger(name):
    """Returns a logger with the given name."""
    return logging.getLogger(name)
