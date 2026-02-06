import asyncio
import sys
import os

# Add the project root to sys.path so we can import aniplay
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from aniplay.database.db import DatabaseManager
from aniplay.utils.db_migrator import DatabaseMigrator
from aniplay.config import DEFAULT_LIBRARY_PATH

async def main():
    db_manager = DatabaseManager()
    await db_manager.initialize()
    
    migrator = DatabaseMigrator(db_manager)
    
    path = DEFAULT_LIBRARY_PATH
    dry_run = True
    
    args = sys.argv[1:]
    if "--apply" in args:
        dry_run = False
        args.remove("--apply")
    
    if args:
        path = args[0]
        
    print(f"\nStarting Database Path Migration: {path}")
    if dry_run:
        print("[DRY RUN] No changes will be saved to the database.")
    print("-" * 60)
    
    results = await migrator.migrate_paths(path, dry_run=dry_run)
    
    if results["updated"]:
        print(f"Found {len(results['updated'])} episodes that moved:")
        for up in results["updated"][:15]:
            merge_tag = " [Merged]" if up["merged"] else ""
            print(f"  [M]{merge_tag} {up['series_hint']}: {os.path.basename(up['old_path'])} -> {os.path.basename(up['new_path'])}")
        
        if len(results["updated"]) > 15:
            print(f"  ... and {len(results['updated']) - 15} more.")
    else:
        print("No moved episodes detected.")
        
    print("\n" + "=" * 60)
    print(f"Migration Summary:")
    print(f"  Episodes Updated:    {len(results['updated'])}")
    print(f"  Episodes Unchanged:  {results['not_moved']}")
    print(f"  Files Not Found:     {len(results['missing_in_physical'])}")
    if results["failed"]:
        print(f"  Errors:              {len(results['failed'])}")
    print("=" * 60 + "\n")
    
    if dry_run and results["updated"]:
        print("To actually apply these changes and preserve your data, run with --apply")
    elif not dry_run:
        print("Migration complete! Your watch progress has been preserved.")

if __name__ == "__main__":
    asyncio.run(main())
