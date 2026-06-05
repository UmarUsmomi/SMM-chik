import httpx
import logging
import feedparser
from typing import List, Dict, Any
from smm_engine.scrapers.base import BaseScraper, NewsItem

logger = logging.getLogger(__name__)

class HabrRssScraper(BaseScraper):
    """Example Plugin Scraper that parses the Habr (habr.com) RSS feed"""
    async def scrape(self) -> List[NewsItem]:
        if not self.config.get("enabled", True):
            return []

        news_items = []
        limit = self.config.get("limit", 5)
        
        # Habr RSS feed URL (popular / interesting posts)
        url = "https://habr.com/ru/rss/all/all/"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SMMAutomator/1.0"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=12)
                if resp.status_code == 200:
                    # Parse RSS XML from response body
                    feed = feedparser.parse(resp.text)
                    entries = feed.entries[:limit]
                    
                    for entry in entries:
                        item = self._parse_entry(entry)
                        if item:
                            news_items.append(item)
                else:
                    logger.warning(f"Habr RSS Scraper failed. Status: {resp.status_code}")
        except Exception as e:
            logger.error(f"Error scraping Habr RSS feed: {e}")
            
        logger.info(f"Habr RSS Scraper: found {len(news_items)} items")
        return news_items

    def _parse_entry(self, entry: Dict[str, Any]) -> NewsItem:
        title = entry.get("title")
        url = entry.get("link")
        entry_id = entry.get("id")
        
        if not title or not entry_id or not url:
            return None
            
        # Clean id (Habr ID is often a URL like 'https://habr.com/ru/articles/123456/')
        # Extract article number if possible
        import re
        match = re.search(r'/post/(\d+)/|/articles/(\d+)/', entry_id)
        article_id = match.group(1) or match.group(2) if match else entry_id
        
        raw_data = {
            "description": entry.get("summary", ""),
            "author": entry.get("author", "Unknown"),
            "tags": [tag.get("term", "") for tag in entry.get("tags", [])] if entry.get("tags") else ["habr"],
            "published": entry.get("published", "")
        }
        
        return NewsItem(
            source="habr_rss",
            source_id=article_id,
            title=title,
            url=url,
            raw_data=raw_data
        )
