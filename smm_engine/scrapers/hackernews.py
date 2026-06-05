import httpx
import logging
from typing import List, Dict, Any
from urllib.parse import quote_plus
from smm_engine.scrapers.base import BaseScraper, NewsItem

logger = logging.getLogger(__name__)

class HackerNewsScraper(BaseScraper):
    async def scrape(self) -> List[NewsItem]:
        if not self.config.get("enabled", True):
            return []

        news_items = []
        queries = self.config.get("queries", [])
        limit = self.config.get("limit", 15)
        min_score = self.config.get("min_score", 50)
        
        async with httpx.AsyncClient() as client:
            # 1. Scrape front page first (always interesting)
            try:
                url = f"https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage={limit}"
                resp = await client.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    for hit in data.get("hits", []):
                        item = self._parse_hit(hit)
                        if item and hit.get("points", 0) >= min_score:
                            news_items.append(item)
            except Exception as e:
                logger.error(f"Error scraping HackerNews front page: {e}")

            # 2. Scrape keyword searches
            for query in queries:
                try:
                    q_encoded = quote_plus(query)
                    url = f"https://hn.algolia.com/api/v1/search?query={q_encoded}&tags=story&hitsPerPage={limit}"
                    resp = await client.get(url, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        for hit in data.get("hits", []):
                            item = self._parse_hit(hit)
                            if item and hit.get("points", 0) >= (min_score // 2): # lower threshold for keyword searches
                                news_items.append(item)
                except Exception as e:
                    logger.error(f"Error searching HackerNews for '{query}': {e}")
                    
        # Deduplicate within this run
        seen = set()
        unique_items = []
        for item in news_items:
            if item.source_id not in seen:
                seen.add(item.source_id)
                unique_items.append(item)
                
        logger.info(f"HackerNews Scraper: found {len(unique_items)} items")
        return unique_items

    def _parse_hit(self, hit: Dict[str, Any]) -> NewsItem:
        title = hit.get("title")
        url = hit.get("url")
        object_id = hit.get("objectID")
        
        if not title or not object_id:
            return None
            
        # If no URL, it's a Text/Ask HN post, link to the HN page itself
        if not url:
            url = f"https://news.ycombinator.com/item?id={object_id}"
            
        # Put relevant metadata in raw_data
        raw_data = {
            "points": hit.get("points", 0),
            "num_comments": hit.get("num_comments", 0),
            "author": hit.get("author"),
            "created_at_i": hit.get("created_at_i"),
            "story_text": hit.get("story_text", "")
        }
        
        return NewsItem(
            source="hackernews",
            source_id=str(object_id),
            title=title,
            url=url,
            raw_data=raw_data
        )
