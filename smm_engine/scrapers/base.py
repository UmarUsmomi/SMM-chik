from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List

@dataclass
class NewsItem:
    source: str
    source_id: str
    title: str
    url: str
    raw_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

class BaseScraper:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    async def scrape(self) -> List[NewsItem]:
        """Scrapes news items from the source"""
        raise NotImplementedError("Scrapers must implement the scrape method")
