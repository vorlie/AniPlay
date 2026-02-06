import asyncio
import os
from pathlib import Path
from ..config import DEFAULT_LIBRARY_PATH
from ..utils.cleanup_manager import CleanupManager

async def run_cleanup(library_path: str = DEFAULT_LIBRARY_PATH, dry_run: bool = True):
    manager = CleanupManager(dry_run=dry_run)
    root = Path(library_path)
    
    if not root.exists():
        print(f"Error: Library path '{library_path}' does not exist.")
        return

    print(f"\nScanning for Jellyfin junk files in: {library_path}")
    if dry_run:
        print("[DRY RUN] No files will be actually deleted.")
    print("-" * 60)

    junk_files = manager.scan_for_junk(library_path)
    
    if not junk_files:
        print("No junk files found. Your library is clean!")
        return

    print(f"Found {len(junk_files)} potential junk files:")
    for f in junk_files[:20]: # Show first 20
        print(f"  - {f.name} (in {f.parent.name})")
    
    if len(junk_files) > 20:
        print(f"  ... and {len(junk_files) - 20} more.")

    total_size_mb = sum(f.stat().st_size for f in junk_files) / (1024 * 1024)
    print(f"\nTotal potential space to save: {total_size_mb:.2f} MB")

    if dry_run:
        print("\nTo actually delete these files, run with --apply")
    else:
        print("\nDeleting files...")
        results = manager.cleanup(junk_files)
        print(f"Successfully deleted {len(results['deleted'])} files.")
        if results["failed"]:
            print(f"Failed to delete {len(results['failed'])} files. Check logs.")

if __name__ == "__main__":
    import sys
    path = DEFAULT_LIBRARY_PATH
    dry_run = True
    
    args = sys.argv[1:]
    if "--apply" in args:
        dry_run = False
        args.remove("--apply")
    
    if args:
        path = args[0]
    
    asyncio.run(run_cleanup(path, dry_run))
