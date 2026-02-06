import os
import asyncio
from pathlib import Path
from ..config import DEFAULT_LIBRARY_PATH
from ..utils.org_analyzer import OrgAnalyzer

async def run_check(library_path: str = DEFAULT_LIBRARY_PATH):
    analyzer = OrgAnalyzer()
    root = Path(library_path)
    
    if not root.exists():
        print(f"Error: Library path '{library_path}' does not exist.")
        return

    print(f"\nScanning library for organization issues: {library_path}")
    print("-" * 60)

    series_folders = [f for f in root.iterdir() if f.is_dir()]
    
    issue_count = 0
    clean_count = 0
    
    for folder in series_folders:
        # print(f"Checking {folder.name}...")
        results = analyzer.analyze_series(str(folder))
        
        if results["status"] == "issues":
            issue_count += 1
            print(f"\n[!] {folder.name}")
            for issue in results["issues"]:
                print(f"  - {issue['message']}")
                if "files" in issue:
                    print(f"    Possible culprits: {', '.join(issue['files'])}")
        elif results["status"] == "ok":
            clean_count += 1
        # Skip empty folders or non-anime folders without noise

    print("\n" + "=" * 60)
    print(f"Summary:")
    print(f"  Total Series Checked: {len(series_folders)}")
    print(f"  Clean Series:         {clean_count}")
    print(f"  Series with Issues:   {issue_count}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    import sys
    path = DEFAULT_LIBRARY_PATH
    if len(sys.argv) > 1:
        path = sys.argv[1]
    
    asyncio.run(run_check(path))
