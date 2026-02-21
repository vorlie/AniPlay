import logging
import os
import sys
from datetime import datetime
from pathlib import Path

def setup_logging(level=logging.INFO, log_to_file=True):
    """
    Sets up a centralized logging system for AniPlay.
    Logs to console and optionally to a file.
    """
    # Create logs directory if it doesn't exist
    log_file = Path("aniplay.log")
    
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
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Silence noisy third-party loggers
    logging.getLogger("aiosqlite").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("charset_normalizer").setLevel(logging.WARNING)

    logging.info(f"Logging initialized. Level: {logging.getLevelName(level)}, File: {log_file}")

def get_logger(name):
    """Returns a logger with the given name."""
    return logging.getLogger(name)
