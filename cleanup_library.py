import asyncio
import sys
import os

# Add the project root to sys.path so we can import aniplay
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from aniplay.cli.cleanup import run_cleanup
from aniplay.config import DEFAULT_LIBRARY_PATH

if __name__ == "__main__":
    path = DEFAULT_LIBRARY_PATH
    dry_run = True
    
    args = sys.argv[1:]
    if "--apply" in args:
        dry_run = False
        args.remove("--apply")
    
    if args:
        path = args[0]
    
    asyncio.run(run_cleanup(path, dry_run))
