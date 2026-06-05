import httpx
import logging
import html
import re
from typing import List, Dict, Any
from smm_engine.scrapers.base import BaseScraper, NewsItem

logger = logging.getLogger(__name__)

class SteamNewsScraper(BaseScraper):
    async def scrape(self) -> List[NewsItem]:
        if not self.config.get("enabled", True):
            return []

        news_items = []
        apps = self.config.get("apps", {730: "Counter-Strike 2"})
        limit = self.config.get("limit", 3)
        
        async with httpx.AsyncClient() as client:
            for app_id, game_name in apps.items():
                try:
                    url = f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v0002/?appid={app_id}&count={limit}&format=json"
                    resp = await client.get(url, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        news_items_list = data.get("appnews", {}).get("newsitems", [])
                        for news in news_items_list:
                            item = self._parse_news(news, app_id, game_name)
                            if item:
                                news_items.append(item)
                except Exception as e:
                    logger.error(f"Error scraping Steam News for app {app_id} ({game_name}): {e}")
                    
        # Deduplicate
        seen = set()
        unique_items = []
        for item in news_items:
            if item.source_id not in seen:
                seen.add(item.source_id)
                unique_items.append(item)
                
        logger.info(f"Steam News Scraper: found {len(unique_items)} items")
        return unique_items

    def _clean_contents(self, text: str) -> str:
        """Helper to remove Steam BBCode tags and HTML tags"""
        if not text:
            return ""
        # Remove BBCode tags
        text = re.sub(r'\[url=.*?\](.*?)\[/url\]', r'\1', text)
        text = re.sub(r'\[img\].*?\[/img\]', '', text)
        text = re.sub(r'\[b\](.*?)\[/b\]', r'\1', text)
        text = re.sub(r'\[i\](.*?)\[/i\]', r'\1', text)
        text = re.sub(r'\[.*?\]', '', text)
        # Decode HTML entities and strip tags
        text = html.unescape(text)
        text = re.sub(r'<[^>]*>', '', text)
        return text.strip()

    def _parse_news(self, news: Dict[str, Any], app_id: int, game_name: str) -> NewsItem:
        title = news.get("title")
        url = news.get("url")
        gid = news.get("gid")
        
        if not title or not gid or not url:
            return None
            
        contents = self._clean_contents(news.get("contents", ""))
        
        raw_data = {
            "game_name": game_name,
            "app_id": app_id,
            "author": news.get("author", ""),
            "feedlabel": news.get("feedlabel", ""),
            "contents": contents[:500],  # only keep preview for memory/token efficiency
            "date": news.get("date"),
        }
        
        return NewsItem(
            source="steam",
            source_id=str(gid),
            title=f"[{game_name}] {title}",
            url=url,
            raw_data=raw_data
        )
