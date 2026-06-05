import logging
from typing import Dict, Any, List

from smm_engine.config import SOURCES_CONFIG, AUTO_PUBLISH_THRESHOLD, QUEUE_THRESHOLD
from smm_engine.storage.database import DatabaseManager
from smm_engine.scrapers.base import NewsItem
from smm_engine.scrapers import run_all_scrapers
from smm_engine.analyzers.scorer import NewsScorer
from smm_engine.analyzers.duplicates import Deduplicator
from smm_engine.content.adapter import ContentAdapter
from smm_engine.publishers.telegram_pub import TelegramPublisher
from smm_engine.publishers.threads_pub import ThreadsPublisher

logger = logging.getLogger(__name__)

class SMMPipeline:
    def __init__(self):
        self.db = DatabaseManager()
        self.scorer = NewsScorer()
        self.deduplicator = Deduplicator(similarity_threshold=0.75)
        self.adapter = ContentAdapter()
        self.publisher = TelegramPublisher()
        self.threads_pub = ThreadsPublisher()

    async def run(self) -> Dict[str, Any]:
        """Runs one full cycle of the SMM pipeline"""
        logger.info("Starting SMM pipeline run...")
        
        summary = {
            "scraped": 0,
            "duplicates": 0,
            "processed": 0,
            "queued": 0,
            "published": 0,
            "errors": 0
        }

        # 1. Scrape all sources
        try:
            scraped_items = await run_all_scrapers(SOURCES_CONFIG)
            summary["scraped"] = len(scraped_items)
        except Exception as e:
            logger.error(f"Error during scraping phase: {e}")
            summary["errors"] += 1
            return summary

        # 2. Load recent items for fuzzy deduplication
        try:
            recent_items = self.db.get_recent_items(limit=150)
        except Exception as e:
            logger.error(f"Error loading recent items: {e}")
            recent_items = []

        new_items_processed = []
        scored_count = 0
        max_scores_per_run = 10  # Hard limit to prevent rate limits and save API quota

        # 3. Filter and score items
        for item in scraped_items:
            try:
                # A. Exact duplicate check
                if self.db.is_duplicate(item.source, item.source_id, item.url):
                    summary["duplicates"] += 1
                    continue

                # B. Fuzzy title duplicate check
                duplicate_found = self.deduplicator.find_duplicate(item.title, recent_items)
                if duplicate_found:
                    summary["duplicates"] += 1
                    # Save to DB as duplicate/rejected directly to prevent re-processing
                    self.db.save_news_item(item.source, item.source_id, item.title, item.url, item.raw_data)
                    continue

                # C. Hard limit on new items scored per run
                if scored_count >= max_scores_per_run:
                    logger.info(f"Reached max_scores_per_run ({max_scores_per_run}). Skipping remaining new items for this run.")
                    break  # Stop processing further new items to protect API quota

                # D. Save news item to DB
                item_id = self.db.save_news_item(item.source, item.source_id, item.title, item.url, item.raw_data)
                if not item_id:
                    continue

                # E. Score the news item using Gemini
                score_res = await self.scorer.score_item(item)
                score = score_res.get("total", 0)
                reason = score_res.get("reason", "No reason provided")
                
                # F. Update scoring in database
                self.db.update_scoring(item_id, score, reason, status='parsed')
                
                # Retrieve full saved object to keep track
                db_item = self.db.get_by_id(item_id)
                new_items_processed.append(db_item)
                summary["processed"] += 1
                scored_count += 1
                
                # Update recent items for subsequent comparisons in the same loop
                recent_items.append({"title": item.title, "url": item.url})
                
            except Exception as e:
                logger.error(f"Error processing item '{item.title}': {e}")
                summary["errors"] += 1

        # 4. Content Adaptation & Publishing Decision
        # Check all un-published items in database to find the best candidate
        # This includes items parsed during this run AND previously queued/parsed but not published
        try:
            # Get parsed items
            parsed_items = self.db.get_queue(status='parsed', limit=30)
            all_candidates = parsed_items + [x for x in new_items_processed if x.get("status") == "parsed"]
            
            # Sort candidates by score descending
            all_candidates = sorted(all_candidates, key=lambda x: x.get("score", 0), reverse=True)
            
            if not all_candidates:
                logger.info("No candidates for publication or review in this run.")
                return summary

            adapted_count = 0
            max_adaptations_per_run = 3

            # Process candidates according to threshold
            for candidate in all_candidates:
                score = candidate.get("score", 0)
                item_id = candidate.get("id")
                
                # Reconstruct NewsItem for the adapter
                news_item = NewsItem(
                    source=candidate.get("source"),
                    source_id=candidate.get("source_id"),
                    title=candidate.get("title"),
                    url=candidate.get("url"),
                    raw_data={} # raw_data not needed for adaptation, title/url/source is enough
                )
                
                is_paused = self.db.get_setting("is_paused", "false") == "true"
                
                if score >= AUTO_PUBLISH_THRESHOLD and not is_paused:
                    # A. Auto-Publish!
                    logger.info(f"Auto-publishing candidate '{candidate.get('title')}' with score {score}")
                    
                    adapted = await self.adapter.adapt_news(news_item)
                    if adapted:
                        success = await self.publisher.publish_post_with_cover(adapted["title"], adapted["text"])
                        if success:
                            # Also publish to Threads
                            await self.threads_pub.publish_post(f"{adapted['title']}\n\n{adapted['text']}")
                            self.db.save_adapted_content(item_id, adapted["title"], adapted["text"], status='published')
                            self.db.mark_published(item_id)
                            summary["published"] += 1
                            # We only publish one story per run to avoid spamming the channel
                            break
                        else:
                            # If publishing failed, save adapted content and keep in queue
                            self.db.save_adapted_content(item_id, adapted["title"], adapted["text"], status='pending_review')
                            summary["queued"] += 1
                
                elif score >= QUEUE_THRESHOLD:
                    # B. Add to review queue
                    logger.info(f"Queuing candidate '{candidate.get('title')}' with score {score}")
                    
                    # If we've already adapted enough items in this run, keep this one in 'parsed' status
                    # so it will be adapted/processed in the next run.
                    if adapted_count >= max_adaptations_per_run:
                        logger.info(f"Skipping adaptation for '{candidate.get('title')}' in this run (max_adaptations_per_run reached).")
                        continue
                    
                    # Adapt text beforehand so it is ready for approval in Telegram Bot
                    adapted = await self.adapter.adapt_news(news_item)
                    if adapted:
                        self.db.save_adapted_content(item_id, adapted["title"], adapted["text"], status='pending_review')
                        summary["queued"] += 1
                        adapted_count += 1
                    else:
                        self.db.update_scoring(item_id, score, candidate.get("score_reason"), status='pending_review')
                        summary["queued"] += 1
                else:
                    # C. Reject
                    self.db.update_scoring(item_id, score, candidate.get("score_reason"), status='rejected')
                    
        except Exception as e:
            logger.error(f"Error in decision/publishing phase: {e}")
            summary["errors"] += 1

        logger.info(f"Pipeline run complete: {summary}")
        return summary
