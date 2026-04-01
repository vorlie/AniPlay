import json
import time
import pytest
import respx
from httpx import Response
from aniplay.utils import anilist_client

_SEARCH_RESP = {
    "data": {
        "Page": {
            "media": [
                {
                    "id": 123,
                    "title": {"romaji": "Romaji", "english": "English", "native": "Native"},
                    "episodes": 24,
                    "status": "FINISHED",
                    "averageScore": 85,
                    "coverImage": {"large": "https://img/large.jpg", "medium": "https://img/med.jpg"},
                    "nextAiringEpisode": None,
                    "genres": ["Action"],
                    "description": "desc"
                }
            ]
        }
    }
}

_ID_RESP = {"data": {"Media": _SEARCH_RESP["data"]["Page"]["media"][0]}}

@respx.mock
@pytest.mark.asyncio
async def test_search_parses_results():
    route = respx.post(anilist_client._ENDPOINT).mock(return_value=Response(200, json=_SEARCH_RESP))
    results = await anilist_client.search("Romaji")
    assert route.called
    assert isinstance(results, list)
    r = results[0]
    assert r["anilist_id"] == 123
    assert r["title_romaji"] == "Romaji"
    assert r["display_title"] == "English"  # English preferred
    assert r["cover_url"].startswith("https://")
    assert r["episodes"] == 24
    assert abs(r["average_score"] - 8.5) < 0.001

@respx.mock
@pytest.mark.asyncio
async def test_get_by_id_returns_parsed():
    route = respx.post(anilist_client._ENDPOINT).mock(return_value=Response(200, json=_ID_RESP))
    obj = await anilist_client.get_by_id(123)
    assert route.called
    assert obj["anilist_id"] == 123
    assert obj["display_title"] == "English"

@respx.mock
@pytest.mark.asyncio
async def test_search_handles_http_error():
    route = respx.post(anilist_client._ENDPOINT).mock(return_value=Response(500, json={"errors": []}))
    results = await anilist_client.search("Whatever")
    assert route.called
    assert results == []  # client returns empty list on errors

@respx.mock
@pytest.mark.asyncio
async def test_search_cache_hit(monkeypatch):
    # first call -> network; second call -> cached, so route called only once
    route = respx.post(anilist_client._ENDPOINT).mock(return_value=Response(200, json=_SEARCH_RESP))
    # ensure cache empty
    anilist_client._CACHE.clear()
    r1 = await anilist_client.search("CacheMe")
    assert route.called
    route.calls.reset()
    r2 = await anilist_client.search("  CacheMe  ")  # trimmed + case-insensitive should hit same cache
    assert route.calls.call_count == 0
    assert r1 == r2

@respx.mock
@pytest.mark.asyncio
async def test_cache_ttl_expires(monkeypatch):
    anilist_client._CACHE.clear()
    # seed cache with old timestamp
    key = "search:ttltest"
    anilist_client._CACHE[key] = (time.time() - (anilist_client._CACHE_TTL + 10), [{"anilist_id": 1}])
    route = respx.post(anilist_client._ENDPOINT).mock(return_value=Response(200, json=_SEARCH_RESP))
    res = await anilist_client.search("ttltest")
    assert route.called