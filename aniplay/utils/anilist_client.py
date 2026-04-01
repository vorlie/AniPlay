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

"""
AniList public GraphQL client (no auth required).
Provides search and metadata lookup against anilist.co.
"""

import httpx
import time
from typing import List, Dict, Optional, Any
from .logger import get_logger

logger = get_logger(__name__)

_ENDPOINT = "https://graphql.anilist.co"
_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

# Simple in-process cache: key -> (fetched_at, data)
_CACHE: Dict[str, tuple] = {}
_CACHE_TTL = 900  # 15 minutes


def _cache_get(key: str) -> Optional[Any]:
    if key in _CACHE:
        fetched_at, data = _CACHE[key]
        if time.time() - fetched_at < _CACHE_TTL:
            return data
        del _CACHE[key]
    return None


def _cache_set(key: str, data: Any):
    _CACHE[key] = (time.time(), data)


_SEARCH_QUERY = """
query ($search: String, $page: Int) {
  Page(page: $page, perPage: 10) {
    media(search: $search, type: ANIME) {
      id
      title { romaji english native }
      episodes
      status
      averageScore
      coverImage { large medium }
      nextAiringEpisode { episode timeUntilAiring }
      genres
      description(asHtml: false)
    }
  }
}
"""

_ID_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    title { romaji english native }
    episodes
    status
    averageScore
    coverImage { large medium }
    nextAiringEpisode { episode timeUntilAiring }
    genres
    description(asHtml: false)
  }
}
"""


def _parse_media(item: dict) -> dict:
    """Normalise a raw AniList Media object into a flat dict."""
    title_obj = item.get("title") or {}
    cover = item.get("coverImage") or {}
    nae = item.get("nextAiringEpisode")
    return {
        "anilist_id": item.get("id"),
        "title_romaji": title_obj.get("romaji"),
        "title_english": title_obj.get("english"),
        "title_native": title_obj.get("native"),
        # Prefer English title, fall back to romaji
        "display_title": title_obj.get("english") or title_obj.get("romaji") or "",
        "episodes": item.get("episodes"),          # None if unknown/ongoing
        "status": item.get("status"),              # RELEASING / FINISHED / NOT_YET_RELEASED etc.
        "average_score": (item.get("averageScore") or 0) / 10.0 if item.get("averageScore") else None,
        "cover_url": cover.get("large") or cover.get("medium"),
        "next_episode": nae["episode"] if nae else None,
        "next_episode_airing": nae["timeUntilAiring"] if nae else None,  # seconds from now
        "genres": item.get("genres") or [],
        "description": item.get("description") or "",
    }


async def search(name: str) -> List[dict]:
    """Search AniList for anime matching *name*. Returns up to 10 results."""
    # Normalize whitespace and case for cache key (trim, collapse internal spaces)
    n = (name or "")
    # Two normalization forms: collapse internal whitespace, and simple strip+lower
    normalized_collapsed = " ".join(n.split()).lower().strip()
    normalized_simple = n.lower().strip()
    # Try several normalization forms when looking up cache to be tolerant
    # First try direct variants
    variants = [normalized_collapsed, normalized_simple, n.strip().lower(), " ".join(n.split()).lower()]
    for v in variants:
        cached = _cache_get(f"search:{v}")
        if cached is not None:
            return cached

    # As a fallback, scan existing cache keys and compare collapsed-normalized forms
    target = normalized_collapsed
    for k in list(_CACHE.keys()):
        if not k.startswith("search:"):
            continue
        kval = k[len("search:"):]
        if " ".join(kval.split()).lower().strip() == target:
            cached = _cache_get(k)
            if cached is not None:
                return cached
    # Prepare deduplicated variants for storing
    seen = set()
    variants_unique = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            variants_unique.append(v)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _ENDPOINT,
                headers=_HEADERS,
                json={"query": _SEARCH_QUERY, "variables": {"search": name, "page": 1}},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", {}).get("Page", {}).get("media") or []
            results = [_parse_media(m) for m in items]
            # Store under all variant keys so equivalent queries hit the cache
            for v in variants_unique:
                try:
                    _cache_set(f"search:{v}", results)
                except Exception:
                    pass
            return results
    except Exception as e:
        logger.error(f"AniList search error for '{name}': {e}")
        return []


async def get_by_id(anilist_id: int) -> Optional[dict]:
    """Fetch a single show's public metadata by AniList ID."""
    cache_key = f"id:{anilist_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _ENDPOINT,
                headers=_HEADERS,
                json={"query": _ID_QUERY, "variables": {"id": anilist_id}},
            )
            resp.raise_for_status()
            data = resp.json()
            item = data.get("data", {}).get("Media")
            if not item:
                return None
            result = _parse_media(item)
            _cache_set(cache_key, result)
            return result
    except Exception as e:
        logger.error(f"AniList ID lookup error for {anilist_id}: {e}")
        return None
