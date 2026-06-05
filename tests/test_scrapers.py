import pytest
from smm_engine.config import SOURCES_CONFIG
from smm_engine.scrapers.hackernews import HackerNewsScraper
from smm_engine.scrapers.devto import DevToScraper
from smm_engine.scrapers.steam_news import SteamNewsScraper
from smm_engine.scrapers.github_trending import GitHubTrendingScraper
from smm_engine.scrapers.gamersnexus import GamersNexusScraper
from smm_engine.scrapers.base import NewsItem

@pytest.mark.asyncio
async def test_hackernews_scraper():
    cfg = SOURCES_CONFIG.get("sources", {}).get("hackernews", {})
    # Override limit to 2 for quick testing
    cfg["limit"] = 2
    scraper = HackerNewsScraper(cfg)
    items = await scraper.scrape()
    
    assert isinstance(items, list)
    if items:
        item = items[0]
        assert isinstance(item, NewsItem)
        assert item.source == "hackernews"
        assert item.source_id is not None
        assert item.title is not None
        assert item.url is not None
        assert "points" in item.raw_data

@pytest.mark.asyncio
async def test_devto_scraper():
    cfg = SOURCES_CONFIG.get("sources", {}).get("devto", {})
    cfg["limit"] = 2
    scraper = DevToScraper(cfg)
    items = await scraper.scrape()
    
    assert isinstance(items, list)
    if items:
        item = items[0]
        assert isinstance(item, NewsItem)
        assert item.source == "devto"
        assert item.source_id is not None
        assert item.title is not None
        assert item.url is not None
        assert "reactions" in item.raw_data

@pytest.mark.asyncio
async def test_steam_news_scraper():
    cfg = SOURCES_CONFIG.get("sources", {}).get("steam", {})
    cfg["limit"] = 1
    # CS2 Game App ID
    cfg["apps"] = {730: "Counter-Strike 2"}
    scraper = SteamNewsScraper(cfg)
    items = await scraper.scrape()
    
    assert isinstance(items, list)
    if items:
        item = items[0]
        assert isinstance(item, NewsItem)
        assert item.source == "steam"
        assert "game_name" in item.raw_data
        assert item.raw_data["game_name"] == "Counter-Strike 2"

@pytest.mark.asyncio
async def test_github_trending_scraper():
    cfg = SOURCES_CONFIG.get("sources", {}).get("github", {})
    cfg["limit"] = 1
    scraper = GitHubTrendingScraper(cfg)
    items = await scraper.scrape()
    
    assert isinstance(items, list)
    if items:
        item = items[0]
        assert isinstance(item, NewsItem)
        assert item.source == "github"
        assert "stars" in item.raw_data

@pytest.mark.asyncio
async def test_gamersnexus_scraper():
    cfg = SOURCES_CONFIG.get("sources", {}).get("gamersnexus", {})
    cfg["limit"] = 1
    scraper = GamersNexusScraper(cfg)
    items = await scraper.scrape()
    
    assert isinstance(items, list)
    if items:
        item = items[0]
        assert isinstance(item, NewsItem)
        assert item.source == "gamersnexus"
        assert "summary" in item.raw_data
