import asyncio
import sys
import os

# Add the project root to sys.path so we can import aniplay
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from aniplay.cli.org_check import run_check
from aniplay.config import DEFAULT_LIBRARY_PATH

if __name__ == "__main__":
    path = DEFAULT_LIBRARY_PATH
    if len(sys.argv) > 1:
        path = sys.argv[1]
    
    asyncio.run(run_check(path))
