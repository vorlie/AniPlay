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

import httpx
import json
import re
import asyncio
from typing import List, Dict, Any
from ..utils.logger import get_logger

logger = get_logger(__name__)

class AniScraper:
    def __init__(self):
        self.base_url = "allanime.day"
        self.api_url = f"https://api.{self.base_url}"
        self.referer = "https://allmanga.to"
        self.agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
        self.headers = {
            "User-Agent": self.agent,
            "Referer": self.referer
        }
        
        # Hex to char mapping from ani-cli
        self.hex_map = {
            "79": "A", "7a": "B", "7b": "C", "7c": "D", "7d": "E", "7e": "F", "7f": "G", "70": "H",
            "71": "I", "72": "J", "73": "K", "74": "L", "75": "M", "76": "N", "77": "O", "68": "P",
            "69": "Q", "6a": "R", "6b": "S", "6c": "T", "6d": "U", "6e": "V", "6f": "W", "60": "X",
            "61": "Y", "62": "Z", "59": "a", "5a": "b", "5b": "c", "5c": "d", "5d": "e", "5e": "f",
            "5f": "g", "50": "h", "51": "i", "52": "j", "53": "k", "54": "l", "55": "m", "56": "n",
            "57": "o", "48": "p", "49": "q", "4a": "r", "4b": "s", "4c": "t", "4d": "u", "4e": "v",
            "4f": "w", "40": "x", "41": "y", "42": "z", "08": "0", "09": "1", "0a": "2", "0b": "3",
            "0c": "4", "0d": "5", "0e": "6", "0f": "7", "00": "8", "01": "9", "15": "-", "16": ".",
            "67": "_", "46": "~", "02": ":", "17": "/", "07": "?", "1b": "#", "63": "[", "65": "]",
            "78": "@", "19": "!", "1c": "$", "1e": "&", "10": "(", "11": ")", "12": "*", "13": "+",
            "14": ",", "03": ";", "05": "=", "1d": "%"
        }

    def decode_id(self, hashed_id: str) -> str:
        # Ported from ani-cli's provider_init
        decoded = ""
        # The hashed_id in ani-cli starts with --
        if hashed_id.startswith("--"):
            hashed_id = hashed_id[2:]
            
        for i in range(0, len(hashed_id), 2):
            hex_val = hashed_id[i:i+2]
            decoded += self.hex_map.get(hex_val, "")
            
        return decoded.replace("/clock", "/clock.json")

    async def search(self, query: str, mode: str = "sub") -> List[Dict[str, Any]]:
        search_gql = """
        query( $search: SearchInput $limit: Int $page: Int $translationType: VaildTranslationTypeEnumType $countryOrigin: VaildCountryOriginEnumType ) {
            shows( search: $search limit: $limit page: $page translationType: $translationType countryOrigin: $countryOrigin ) {
                edges {
                    _id
                    name
                    thumbnail
                    availableEpisodes
                    __typename
                }
            }
        }
        """
        variables = {
            "search": {
                "allowAdult": False,
                "allowUnknown": False,
                "query": query
            },
            "limit": 40,
            "page": 1,
            "translationType": mode,
            "countryOrigin": "ALL"
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.api_url}/api",
                params={
                    "variables": json.dumps(variables),
                    "query": search_gql
                },
                headers=self.headers
            )
            data = resp.json()
            return data.get("data", {}).get("shows", {}).get("edges", [])

    async def get_episodes(self, show_id: str, mode: str = "sub", show_name: str = None) -> List[str]:
        # If show_id starts with allanime-, it's a hash and won't work with the API.
        # Try to find the original ID by searching for the name.
        if show_id.startswith("allanime-") and show_name:
            results = await self.search(show_name, mode=mode)
            if results:
                show_id = results[0]['_id']
                logger.info(f"Resolved hashed ID {show_id} via name search for {show_name}")

        episodes_list_gql = """
        query ($showId: String!) {
            show( _id: $showId ) {
                _id
                availableEpisodesDetail
            }
        }
        """
        variables = {"showId": show_id}
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.api_url}/api",
                params={
                    "variables": json.dumps(variables),
                    "query": episodes_list_gql
                },
                headers=self.headers
            )
            data = resp.json()
            details = data.get("data", {}).get("show", {}).get("availableEpisodesDetail", {})
            return sorted(details.get(mode, []), key=lambda x: float(x) if x.replace('.', '', 1).isdigit() else 0)

    async def get_stream_urls(self, show_id: str, episode_no: str, mode: str = "sub", show_name: str = None) -> List[Dict[str, str]]:
        # Handle hashed IDs
        if show_id.startswith("allanime-") and show_name:
            results = await self.search(show_name, mode=mode)
            if results:
                show_id = results[0]['_id']

        episode_embed_gql = """
        query ($showId: String!, $translationType: VaildTranslationTypeEnumType!, $episodeString: String!) {
            episode( showId: $showId translationType: $translationType episodeString: $episodeString ) {
                episodeString
                sourceUrls
            }
        }
        """
        variables = {
            "showId": show_id,
            "translationType": mode,
            "episodeString": episode_no
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.api_url}/api",
                params={
                    "variables": json.dumps(variables),
                    "query": episode_embed_gql
                },
                headers=self.headers
            )
            data = resp.json()
            sources = data.get("data", {}).get("episode", {}).get("sourceUrls", [])
            
            stream_links = []
            for source in sources:
                source_url = source.get("sourceUrl", "")
                source_name = source.get("sourceName", "")
                
                if source_url.startswith("--"):
                    decoded_path = self.decode_id(source_url)
                    try:
                        link_resp = await client.get(
                            f"https://{self.base_url}{decoded_path}",
                            headers=self.headers
                        )
                        link_data = link_resp.json()
                        
                        m3u8_refr = link_data.get("Referer")
                        subtitles = link_data.get("subtitles", [])
                        sub_url = next((s["src"] for s in subtitles if s.get("lang") == "en"), None)
                        
                        raw_links = []
                        # Handle Wixmp/repackager links
                        if "links" in link_data:
                            for link_entry in link_data["links"]:
                                url = link_entry.get("link", "")
                                if "repackager.wixmp.com" in url:
                                    # Example: repackager.wixmp.com/...,720,480,360,.mp4.urlset
                                    match = re.search(r'/,([\d,]+),/', url)
                                    if match:
                                        #base_url = url.replace(f", {match.group(1)},", "")
                                        for q in match.group(1).split(','):
                                            if q:
                                                raw_links.append({
                                                    "url": url.replace(f", {match.group(1)},", f", {q},"),
                                                    "quality": f"{q}p"
                                                })
                                        continue

                                raw_links.append({
                                    "url": url,
                                    "quality": link_entry.get("resolutionStr", "Unknown")
                                })
                        
                        if "hls" in link_data:
                            hls_url = link_data["hls"].get("url")
                            if hls_url:
                                if "master.m3u8" in hls_url:
                                    # Fetch master playlist to find actual streams
                                    try:
                                        m3u8_resp = await client.get(hls_url, headers={"Referer": m3u8_refr or self.referer})
                                        content = m3u8_resp.text
                                        # Basic m3u8 parsing
                                        lines = content.split('\n')
                                        for i in range(len(lines)):
                                            if "#EXT-X-STREAM-INF" in lines[i] and i + 1 < len(lines):
                                                res_match = re.search(r'RESOLUTION=\d+x(\d+)', lines[i])
                                                res = f"{res_match.group(1)}p" if res_match else "HLS"
                                                # Relative or absolute URL
                                                stream_url = lines[i+1].strip()
                                                if not stream_url.startswith("http"):
                                                    stream_url = re.sub(r'/[^/]*$', '/', hls_url) + stream_url
                                                raw_links.append({"url": stream_url, "quality": res})
                                    except Exception as e:
                                        logger.error(f"Error fetching HLS links for {source_name}: {e}")
                                        raw_links.append({"url": hls_url, "quality": "HLS"})
                                else:
                                    raw_links.append({"url": hls_url, "quality": "HLS"})

                        for link in raw_links:
                            url = link["url"]
                            res = link["quality"]
                            if url:
                                referrer = m3u8_refr or self.referer
                                if "tools.fast4speed.rsvp" in url:
                                    referrer = self.referer

                                stream_links.append({
                                    "url": url,
                                    "quality": res,
                                    "source": f"{source_name} ({res})",
                                    "referrer": referrer,
                                    "subtitle": sub_url,
                                    "recommended": source_name == "S-mp4"
                                })
                                
                    except Exception as e:
                        print(f"Error fetching links for {source_name}: {e}")
                else:
                    # Filter out non-hex links if they look like trash, or keep if they're direct
                    # Most legitimate allmanga streams start with --
                    if source_url.startswith("http"):
                        stream_links.append({
                            "url": source_url,
                            "quality": "Direct",
                            "source": source_name,
                            "referrer": self.referer,
                            "subtitle": None
                        })
            
            # Deduplicate by URL
            seen_urls = set()
            unique_links = []
            for link in stream_links:
                if link['url'] not in seen_urls:
                    unique_links.append(link)
                    seen_urls.add(link['url'])

            # Sort links by quality (numeric)
            def quality_key(x):
                res = x['quality'].replace('p', '')
                source = x['source'].lower()
                
                score = 0
                if res.isdigit():
                    score = int(res)
                elif res == "HLS":
                    score = 1
                elif res == "Direct":
                    score = 0
                else:
                    score = 2
                
                # Boost Mp4 sources as they are usually high quality
                if "mp4" in source:
                    score += 5000 
                
                return score
                
            return sorted(unique_links, key=quality_key, reverse=True)

if __name__ == "__main__":
    # Quick test
    async def main():
        scraper = AniScraper()
        print("Searching for Gintama...")
        results = await scraper.search("gintama")
        for res in results:
            print(f"{res['_id']}: {res['name']} ({res.get('availableEpisodes', {}).get('sub', 0)} eps)")
        
        """    
        if results:
            show_id = results[0]['_id']
            print(f"\nGetting episodes for {results[0]['name']}...")
            eps = await scraper.get_episodes(show_id)
            print(f"Total episodes: {len(eps)}")
            if eps:
                print(f"Latest episode: {eps[-1]}")
                print(f"\nGetting stream links for episode {eps[-1]}...")
                links = await scraper.get_stream_urls(show_id, eps[-1])
                for link in links:
                    print(f"[{link['quality']}] {link['source']}: {link['url'][:50]}...")
        """
    asyncio.run(main())
