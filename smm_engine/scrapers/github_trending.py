import httpx
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from smm_engine.scrapers.base import BaseScraper, NewsItem

logger = logging.getLogger(__name__)

class GitHubTrendingScraper(BaseScraper):
    async def scrape(self) -> List[NewsItem]:
        if not self.config.get("enabled", True):
            return []

        news_items = []
        topics = self.config.get("topics", ["ai", "gamedev"])
        limit = self.config.get("limit", 5)
        min_stars = self.config.get("min_stars", 100)
        
        # Calculate date from 7 days ago to fetch only fresh repos
        since_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        async with httpx.AsyncClient() as client:
            headers = {"User-Agent": "Mozilla/5.0"}
            
            for topic in topics:
                try:
                    # Search query
                    q = f"topic:{topic} created:>{since_date} stars:>={min_stars}"
                    url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={limit}"
                    
                    resp = await client.get(url, headers=headers, timeout=15)
                    if resp.status_code == 200:
                        data = resp.json()
                        for repo in data.get("items", []):
                            item = self._parse_repo(repo, topic)
                            if item:
                                news_items.append(item)
                    elif resp.status_code == 403:
                        # Rate limit reached (60 requests/hr for unauthenticated search)
                        logger.warning("GitHub API rate limit hit, skipping further search")
                        break
                except Exception as e:
                    logger.error(f"Error scraping GitHub for topic '{topic}': {e}")
                    
        # Deduplicate
        seen = set()
        unique_items = []
        for item in news_items:
            if item.source_id not in seen:
                seen.add(item.source_id)
                unique_items.append(item)
                
        logger.info(f"GitHub Scraper: found {len(unique_items)} items")
        return unique_items

    def _parse_repo(self, repo: Dict[str, Any], topic: str) -> NewsItem:
        full_name = repo.get("full_name")
        html_url = repo.get("html_url")
        repo_id = repo.get("id")
        
        if not full_name or not repo_id or not html_url:
            return None
            
        raw_data = {
            "name": repo.get("name"),
            "owner": repo.get("owner", {}).get("login"),
            "description": repo.get("description", ""),
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "language": repo.get("language", "N/A"),
            "topic": topic,
            "topics": repo.get("topics", []),
        }
        
        return NewsItem(
            source="github",
            source_id=str(repo_id),
            title=f"[GitHub] {full_name}: {raw_data['description'] or 'No description'}",
            url=html_url,
            raw_data=raw_data
        )
