import asyncio
import os
import tempfile
from unittest.mock import MagicMock, patch, AsyncMock
from smm_engine.scrapers.base import NewsItem
from smm_engine.pipeline import SMMPipeline

async def main():
    # Setup temp DB
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "test_smm.db")
        print(f"Using temp DB: {db_file}")
        
        with patch("smm_engine.storage.database.SQLITE_DB_PATH", db_file):
            # 1. Setup mocked outputs
            mock_scraped = [
                NewsItem(source="hackernews", source_id="hn_1", title="HackerNews Test Title", url="https://hn.com/1"),
                NewsItem(source="devto", source_id="dev_2", title="Devto Test Title", url="https://dev.to/2")
            ]
            
            mock_adapted_res = {
                "title": "Хайповый Заголовок",
                "text": "Это адаптированный текст поста.\n\n#ии #нейросети\n\nИсточник: https://hn.com/1"
            }

            with patch("smm_engine.pipeline.run_all_scrapers", new_callable=AsyncMock) as mock_run_scrapers, \
                 patch("smm_engine.pipeline.NewsScorer") as mock_scorer_class, \
                 patch("smm_engine.pipeline.ContentAdapter") as mock_adapter_class, \
                 patch("smm_engine.pipeline.TelegramPublisher") as mock_publisher_class:
                 
                mock_run_scrapers.return_value = mock_scraped
                
                mock_scorer_inst = MagicMock()
                mock_scorer_inst.score_item = AsyncMock(side_effect=lambda item: {
                    "total": 95 if item.source == "hackernews" else 80,
                    "reason": "High relevance",
                    "relevance": 30,
                    "freshness": 20,
                    "virality": 20,
                    "uniqueness": 10,
                    "quality": 15
                })
                mock_scorer_class.return_value = mock_scorer_inst
                
                mock_adapter_inst = MagicMock()
                mock_adapter_inst.adapt_news = AsyncMock(return_value=mock_adapted_res)
                mock_adapter_class.return_value = mock_adapter_inst
                
                mock_publisher_inst = MagicMock()
                mock_publisher_inst.publish_post_with_cover = AsyncMock(return_value=True)
                mock_publisher_class.return_value = mock_publisher_inst

                pipeline = SMMPipeline()
                print("Running pipeline...")
                summary = await pipeline.run()
                print(f"Summary: {summary}")
                
                # Fetch all DB items to see what statuses they got
                conn = pipeline.db._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id, title, score, status FROM news_items;")
                print("DB news_items:")
                for row in cursor.fetchall():
                    print(row)
                conn.close()

if __name__ == "__main__":
    asyncio.run(main())
