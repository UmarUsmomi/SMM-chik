import asyncio
import logging
from typing import List, Dict, Any

from smm_engine.scrapers.base import NewsItem
from smm_engine.scrapers.hackernews import HackerNewsScraper
from smm_engine.scrapers.devto import DevToScraper
from smm_engine.scrapers.steam_news import SteamNewsScraper
from smm_engine.scrapers.github_trending import GitHubTrendingScraper
from smm_engine.scrapers.gamersnexus import GamersNexusScraper

logger = logging.getLogger(__name__)

async def run_all_scrapers(config: Dict[str, Any]) -> List[NewsItem]:
    """Runs all enabled scrapers concurrently and aggregates findings"""
    sources_config = config.get("sources", {})
    
    scrapers = []
    if sources_config.get("hackernews", {}).get("enabled", True):
        scrapers.append(HackerNewsScraper(sources_config.get("hackernews", {})))
        
    if sources_config.get("devto", {}).get("enabled", True):
        scrapers.append(DevToScraper(sources_config.get("devto", {})))
        
    if sources_config.get("steam", {}).get("enabled", True):
        scrapers.append(SteamNewsScraper(sources_config.get("steam", {})))
        
    if sources_config.get("github", {}).get("enabled", True):
        scrapers.append(GitHubTrendingScraper(sources_config.get("github", {})))
        
    if sources_config.get("gamersnexus", {}).get("enabled", True):
        scrapers.append(GamersNexusScraper(sources_config.get("gamersnexus", {})))

    if not scrapers:
        logger.warning("No scrapers are enabled in config")
        return []

    # Run concurrently
    tasks = [scraper.scrape() for scraper in scrapers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_items = []
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"Scraper execution error: {r}", exc_info=r)
        elif r:
            all_items.extend(r)
            
    return all_items
