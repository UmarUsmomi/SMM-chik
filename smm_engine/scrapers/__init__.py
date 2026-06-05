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

def _load_plugin_scrapers(sources_config: Dict[str, Any]) -> List[Any]:
    """Loads custom scraper plugins dynamically from the plugins/scrapers directory."""
    import importlib
    import pkgutil
    import sys
    from pathlib import Path
    from smm_engine.scrapers.base import BaseScraper
    
    plugin_scrapers = []
    
    plugins_dir = Path("plugins") / "scrapers"
    if not plugins_dir.exists():
        try:
            plugins_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create plugins/scrapers directory: {e}")
            return []
            
    # Add plugins/scrapers to sys.path to resolve imports
    plugins_path_str = str(plugins_dir.resolve())
    if plugins_path_str not in sys.path:
        sys.path.insert(0, plugins_path_str)
        
    logger.info(f"Scanning plugins/scrapers/ at {plugins_path_str}...")
    
    try:
        for finder, name, ispkg in pkgutil.iter_modules([plugins_path_str]):
            try:
                # Import the module dynamically
                module = importlib.import_module(name)
                
                # Inspect all classes in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type) and 
                        issubclass(attr, BaseScraper) and 
                        attr is not BaseScraper
                    ):
                        # Check if this plugin scraper is enabled in config.
                        config_key = name.lower()
                        scraper_config = sources_config.get(config_key, {})
                        
                        # Enable by default if not explicitly disabled
                        if scraper_config.get("enabled", True):
                            logger.info(f"Loaded and enabled plugin scraper class: {attr.__name__} from module: {name}")
                            plugin_scrapers.append(attr(scraper_config))
                        else:
                            logger.info(f"Plugin scraper {attr.__name__} from module {name} is disabled in config.")
            except Exception as e:
                logger.error(f"Error loading plugin module '{name}': {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error scanning plugins directory: {e}", exc_info=True)
        
    return plugin_scrapers

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

    # Load dynamic plugin scrapers
    plugin_scrapers = _load_plugin_scrapers(sources_config)
    scrapers.extend(plugin_scrapers)

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
