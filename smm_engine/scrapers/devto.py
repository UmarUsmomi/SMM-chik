import httpx
import logging
from typing import List, Dict, Any
from smm_engine.scrapers.base import BaseScraper, NewsItem

logger = logging.getLogger(__name__)

class DevToScraper(BaseScraper):
    async def scrape(self) -> List[NewsItem]:
        if not self.config.get("enabled", True):
            return []

        news_items = []
        tags = self.config.get("tags", ["ai", "gamedev"])
        limit = self.config.get("limit", 10)
        min_reactions = self.config.get("min_reactions", 10)
        
        async with httpx.AsyncClient() as client:
            for tag in tags:
                try:
                    url = f"https://dev.to/api/articles?tag={tag}&per_page={limit}"
                    resp = await client.get(url, timeout=10)
                    if resp.status_code == 200:
                        articles = resp.json()
                        for article in articles:
                            reactions = article.get("public_reactions_count", 0)
                            if reactions >= min_reactions:
                                item = self._parse_article(article, tag)
                                news_items.append(item)
                except Exception as e:
                    logger.error(f"Error scraping Dev.to tag '{tag}': {e}")
                    
        # Deduplicate within this run
        seen = set()
        unique_items = []
        for item in news_items:
            if item.source_id not in seen:
                seen.add(item.source_id)
                unique_items.append(item)
                
        logger.info(f"Dev.to Scraper: found {len(unique_items)} items")
        return unique_items

    def _parse_article(self, article: Dict[str, Any], tag: str) -> NewsItem:
        title = article.get("title")
        url = article.get("url")
        article_id = article.get("id")
        
        if not title or not article_id or not url:
            return None
            
        raw_data = {
            "description": article.get("description", ""),
            "reactions": article.get("public_reactions_count", 0),
            "comments": article.get("comments_count", 0),
            "cover_image": article.get("cover_image"),
            "social_image": article.get("social_image"),
            "tags": article.get("tag_list", []),
            "query_tag": tag,
            "readable_publish_date": article.get("readable_publish_date"),
        }
        
        return NewsItem(
            source="devto",
            source_id=str(article_id),
            title=title,
            url=url,
            raw_data=raw_data
        )
