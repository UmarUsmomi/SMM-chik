import httpx
import logging
from typing import List, Dict, Any
from smm_engine.scrapers.base import BaseScraper, NewsItem

logger = logging.getLogger(__name__)

class RedditTechScraper(BaseScraper):
    """Example Plugin Scraper that parses /r/technology hot posts via public JSON API"""
    async def scrape(self) -> List[NewsItem]:
        if not self.config.get("enabled", True):
            return []

        news_items = []
        limit = self.config.get("limit", 5)
        
        # We need a custom user-agent to avoid Reddit's 429 block on default python/httpx user agents
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 SMMAutomator/1.0"
        }
        
        url = f"https://www.reddit.com/r/technology/hot.json?limit={limit}"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    children = data.get("data", {}).get("children", [])
                    for post in children:
                        post_data = post.get("data", {})
                        
                        # Skip pinned posts
                        if post_data.get("stickied"):
                            continue
                            
                        item = self._parse_post(post_data)
                        if item:
                            news_items.append(item)
                else:
                    logger.warning(f"Reddit Scraper failed. Status: {resp.status_code}, Body: {resp.text[:100]}")
        except Exception as e:
            logger.error(f"Error scraping Reddit /r/technology: {e}")
            
        logger.info(f"Reddit Tech Scraper: found {len(news_items)} items")
        return news_items

    def _parse_post(self, post: Dict[str, Any]) -> NewsItem:
        title = post.get("title")
        permalink = post.get("permalink")
        post_id = post.get("id")
        
        if not title or not post_id or not permalink:
            return None
            
        url = f"https://www.reddit.com{permalink}"
        raw_data = {
            "description": post.get("selftext", ""),
            "author": post.get("author"),
            "score": post.get("score", 0),
            "num_comments": post.get("num_comments", 0),
            "tags": ["reddit", "technology"],
            "created_utc": post.get("created_utc")
        }
        
        return NewsItem(
            source="reddit_tech",
            source_id=post_id,
            title=title,
            url=url,
            raw_data=raw_data
        )
