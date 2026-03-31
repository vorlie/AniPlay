import asyncio
from aniplay.utils.nyaa_scraper import NyaaScraper

async def test_search():
    scraper = NyaaScraper()
    print("Testing NyaaScraper search for 'Gintama'...")
    results = await scraper.search("Gintama")
    
    if not results:
        print("FAIL: No results found.")
        return
    
    print(f"SUCCESS: Found {len(results)} results.")
    for i, res in enumerate(results[:3]):
        print(f"{i+1}. {res['name']} ({res['size']}, S:{res['seeders']})")
        assert res['is_nyaa'] is True
        assert res['magnet'] is not None or res['torrent_url'] is not None

async def test_get_stream_urls():
    scraper = NyaaScraper()
    info_hash = "1234567890abcdef1234567890abcdef12345678"
    print(f"Testing NyaaScraper get_stream_urls for hash {info_hash}...")
    urls = await scraper.get_stream_urls(info_hash)
    
    assert len(urls) == 1
    assert urls[0]['is_magnet'] is True
    assert info_hash in urls[0]['url']
    print("SUCCESS: Stream URLs parsed correctly.")

if __name__ == "__main__":
    asyncio.run(test_search())
    asyncio.run(test_get_stream_urls())
