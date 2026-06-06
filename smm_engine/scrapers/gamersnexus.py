import httpx
import feedparser
import logging
from typing import List
from smm_engine.scrapers.base import BaseScraper, NewsItem

logger = logging.getLogger(__name__)

class GamersNexusScraper(BaseScraper):
    async def scrape(self) -> List[NewsItem]:
        if not self.config.get("enabled", True):
            return []

        news_items = []
        rss_url = self.config.get("rss_url", "https://gamersnexus.net/rss.xml")
        limit = self.config.get("limit", 5)
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = await client.get(rss_url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    # Parse RSS feed content
                    feed = feedparser.parse(resp.text)
                    entries = feed.entries[:limit]
                    
                    for entry in entries:
                        item = self._parse_entry(entry)
                        if item:
                            news_items.append(item)
                else:
                    logger.error(f"GamersNexus RSS returned status code {resp.status_code}")
        except Exception as e:
            logger.error(f"Error scraping GamersNexus RSS: {e}")
            
        logger.info(f"GamersNexus Scraper: found {len(news_items)} items")
        return news_items

    def _parse_entry(self, entry) -> NewsItem:
        title = getattr(entry, "title", None)
        link = getattr(entry, "link", None)
        # Unique ID is usually 'id' or link
        entry_id = getattr(entry, "id", link)
        
        if not title or not entry_id or not link:
            return None
            
        summary = getattr(entry, "summary", "")
        published = getattr(entry, "published", "")
        
        # Extract cover image from media elements or summary HTML
        import re
        cover_image = None
        if hasattr(entry, "media_content") and entry.media_content:
            cover_image = entry.media_content[0].get("url")
        elif hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            cover_image = entry.media_thumbnail[0].get("url")
        elif hasattr(entry, "links"):
            for link_item in entry.links:
                if link_item.get("rel") == "enclosure" and "image" in link_item.get("type", ""):
                    cover_image = link_item.get("href")
                    break
        
        if not cover_image and summary:
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
            if img_match:
                cover_image = img_match.group(1)
        
        raw_data = {
            "summary": summary[:500], # Keep a snippet
            "published": published,
            "author": getattr(entry, "author", "GamersNexus Team"),
            "cover_image": cover_image
        }
        
        return NewsItem(
            source="gamersnexus",
            source_id=str(entry_id),
            title=title,
            url=link,
            raw_data=raw_data
        )
