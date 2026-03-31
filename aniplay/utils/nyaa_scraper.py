# AniPlay - Personal media server and player for anime libraries.
# Copyright (C) 2026  Charlie
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import httpx
import xml.etree.ElementTree as ET
import re
import hashlib
from typing import List, Dict, Any, Optional
from .logger import get_logger

logger = get_logger(__name__)

class NyaaScraper:
    def __init__(self):
        self.base_url = "https://nyaa.si"
        # c=1_2: Anime English-translated, f=0: No filter
        self.rss_url = f"{self.base_url}/?page=rss&c=1_2&f=0"
        self.agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.headers = {
            "User-Agent": self.agent
        }
        # XML namespaces for Nyaa extensions
        self.ns = {
            "nyaa": "https://nyaa.si/xmlns/nyaa"
        }

    def _clean_name(self, title: str) -> str:
        """Strips tags and brackets to get the series name."""
        cleaned = re.sub(r'\[.*?\]|\(.*?\)', '', title).strip()
        # Also strip episode numbers like " - 01" at the end
        cleaned = re.sub(r'\s+-\s+\d+.*$', '', cleaned).strip()
        cleaned = re.sub(r'\s+\d+.*$', '', cleaned).strip() # Fallback for space-separated
        return cleaned if cleaned else title

    async def _fetch_raw_results(self, query: str) -> List[Dict[str, Any]]:
        """Internal method to get raw torrent list from Nyaa."""
        url = f"{self.rss_url}&q={query}"
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                resp = await client.get(url, headers=self.headers, timeout=10.0)
                resp.raise_for_status()
                root = ET.fromstring(resp.text)
                items = root.findall(".//item")
                results = []
                for item in items:
                    title = item.find("title").text
                    link = item.find("link").text
                    info_hash_el = item.find("nyaa:infoHash", self.ns)
                    info_hash = info_hash_el.text if info_hash_el is not None else None
                    size = item.find("nyaa:size", self.ns)
                    seeders = item.find("nyaa:seeders", self.ns)
                    leechers = item.find("nyaa:leechers", self.ns)
                    
                    results.append({
                        "id": info_hash if info_hash else link,
                        "name": title,
                        "size": size.text if size is not None else "Unknown",
                        "seeders": seeders.text if seeders is not None else "0",
                        "leechers": leechers.text if leechers is not None else "0",
                        "magnet": link if link.startswith("magnet:") else None,
                        "torrent_url": link if not link.startswith("magnet:") else None,
                    })
                return results
            except Exception as e:
                logger.error(f"Nyaa fetch error: {e}")
                return []

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Searches Nyaa.si and returns a list of grouped series."""
        raw_results = await self._fetch_raw_results(query)
        grouped = {}
        
        for res in raw_results:
            series_name = self._clean_name(res['name'])
            if series_name not in grouped:
                # Generate a stable ID from the series name
                name_hash = hashlib.md5(series_name.encode('utf-8')).hexdigest()[:12]
                show_id = f"nyaa-{name_hash}"
                
                # Use search query as name if it's more specific than the series name
                display_name = query if ("[" in query or "(" in query) and series_name.lower() in query.lower() else series_name
                
                grouped[series_name] = {
                    "_id": show_id,
                    "name": display_name,
                    "thumbnail": None,
                    "size": res['size'],
                    "seeders": res['seeders'],
                    "leechers": res['leechers'],
                    "is_nyaa": True,
                    "is_group": True,
                    "nyaa_query": query # Store original search query
                }
            else:
                # Update stats if this one is "better"
                try:
                    if int(res.get('seeders') or 0) > int(grouped[series_name].get('seeders') or 0):
                        grouped[series_name]['seeders'] = res['seeders']
                        grouped[series_name]['size'] = res['size']
                except: pass
                
        return list(grouped.values())

    def _extract_episode(self, title: str, series_name: str) -> str:
        """Extracts episode number from title."""
        # Try to find number after " - "
        match = re.search(r' - (\d+)', title)
        if match: return str(int(match.group(1)))
        
        # Try to find number after "Episode "
        match = re.search(r'Episode\s+(\d+)', title, re.I)
        if match: return str(int(match.group(1)))
        
        # Try to find any stand-alone number
        match = re.search(r'\s(\d{1,3})\s', title)
        if match: return str(int(match.group(1)))
        
        return "1"

    async def get_episodes(self, show_id: str, show_name: str = None) -> List[str]:
        """Returns a list of unique episode numbers for the series."""
        # Use show_name for search if provided, otherwise fallback to show_id
        search_query = show_name if show_name else show_id
        raw_results = await self._fetch_raw_results(search_query)
        episodes = set()
        for res in raw_results:
            ep = self._extract_episode(res['name'], search_query)
            episodes.add(ep)
        
        # Sort numerically
        return sorted(list(episodes), key=lambda x: int(x) if x.isdigit() else 999)

    async def get_stream_urls(self, show_id: str, episode_no: str = "1", show_name: str = None) -> List[Dict[str, str]]:
        """
        Returns all torrents matching the episode number for the series.
        """
        # Use show_name for search if provided, otherwise fallback to show_id
        search_query = show_name if show_name else show_id
        raw_results = await self._fetch_raw_results(search_query)
        links = []
        
        for res in raw_results:
            ep = self._extract_episode(res['name'], search_query)
            if ep == episode_no:
                magnet_url = res['magnet'] if res['magnet'] else f"magnet:?xt=urn:btih:{res['id']}"
                
                # Add backup trackers if not present
                if "tr=" not in magnet_url:
                    trackers = [
                        "http://nyaa.tracker.wf:7777/announce",
                        "udp://open.stealth.si:80/announce",
                        "udp://tracker.opentrackr.org:1337/announce",
                        "udp://exodus.desync.com:6969/announce",
                        "udp://tracker.torrent.eu.org:451/announce"
                    ]
                    for tr in trackers:
                        magnet_url += f"&tr={tr}"
                
                links.append({
                    "url": magnet_url,
                    "quality": f"Direct (Torrent) - {res['size']}",
                    "source": res['name'],
                    "referrer": self.base_url,
                    "recommended": True if "1080p" in res['name'] else False,
                    "is_magnet": True,
                    "seeders": res['seeders']
                })
        
        # Sort by seeders
        return sorted(links, key=lambda x: int(x.get('seeders', 0)), reverse=True)

if __name__ == "__main__":
    import asyncio
    async def test():
        scraper = NyaaScraper()
        results = await scraper.search("Gintama 720p")
        for res in results[:5]:
            print(f"Title: {res['name']}")
            print(f"Size: {res['size']}, Seeders: {res['seeders']}")
            print(f"Magnet: {res['magnet'][:50]}...")
            print("-" * 20)
            
    asyncio.run(test())
