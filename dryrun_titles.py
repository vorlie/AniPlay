import asyncio
import os
import sys
from aniplay.database.db import DatabaseManager
from aniplay.utils.title_extractor import TitleExtractor

async def dryrun():
    db = DatabaseManager()
    await db.initialize()
    
    episodes = await db.get_all_episodes()
    if not episodes:
        print("No episodes found in database.")
        return

    output_file = "extracted_titles_preview.txt"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# AniPlay Title Extraction Dry-Run Report\n")
        f.write(f"# Total Episodes: {len(episodes)}\n")
        f.write("#" + "-"*80 + "\n\n")
        
        current_series_id = -1
        series_map = {}
        for s in await db.get_all_series():
            series_map[s.id] = s.name

        # Group by series for better readability
        episodes.sort(key=lambda x: (x.series_id, x.season_number or 0, x.episode_number or 0))

        for ep in episodes:
            if ep.series_id != current_series_id:
                current_series_id = ep.series_id
                series_name = series_map.get(ep.series_id, f"Unknown Series (ID: {ep.series_id})")
                f.write(f"\n## SERIES: {series_name}\n")
                f.write("-" * 40 + "\n")
            
            suggested = TitleExtractor.extract(ep.filename)
            s = ep.season_number if ep.season_number is not None else 1
            suggested_title = f"Season {s}: {suggested}" if suggested else None
            status = "[MATCHED]" if suggested else "[FALLBACK]"
            
            f.write(f"{status} Filename: {ep.filename}\n")
            f.write(f"          Suggested: {suggested_title or '(No title extracted)'}\n\n")

    print(f"Dry-run report generated: {output_file}")

if __name__ == "__main__":
    asyncio.run(dryrun())
