import pytest
import os
from unittest.mock import MagicMock, patch, AsyncMock
from smm_engine.scrapers.base import NewsItem
from smm_engine.pipeline import SMMPipeline

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """Sets a temporary sqlite path for tests to avoid cluttering local db"""
    db_file = tmp_path / "test_smm.db"
    with patch("smm_engine.storage.database.SQLITE_DB_PATH", str(db_file)):
        yield str(db_file)

@pytest.mark.asyncio
async def test_smm_pipeline_run():
    # 1. Setup mocked outputs
    mock_scraped = [
        NewsItem(source="hackernews", source_id="hn_1", title="HackerNews Test Title", url="https://hn.com/1"),
        NewsItem(source="devto", source_id="dev_2", title="Devto Test Title", url="https://dev.to/2")
    ]
    
    mock_scorer_res = {"total": 90, "reason": "High relevance", "relevance": 30, "freshness": 20, "virality": 20, "uniqueness": 10, "quality": 10}
    
    mock_adapted_res = {
        "title": "Хайповый Заголовок",
        "text": "Это адаптированный текст поста.\n\n#ии #нейросети\n\nИсточник: https://hn.com/1"
    }

    # 2. Patch functions
    with patch("smm_engine.pipeline.run_all_scrapers", new_callable=AsyncMock) as mock_run_scrapers, \
         patch("smm_engine.pipeline.NewsScorer") as mock_scorer_class, \
         patch("smm_engine.pipeline.ContentAdapter") as mock_adapter_class, \
         patch("smm_engine.pipeline.TelegramPublisher") as mock_publisher_class:
         
        # Configure mocks
        mock_run_scrapers.return_value = mock_scraped
        
        # Return 95 for HackerNews and 80 for Dev.to
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

        # 3. Instantiate pipeline and run
        pipeline = SMMPipeline()
        summary = await pipeline.run()

        # 4. Assert summary results
        assert summary["scraped"] == 2
        assert summary["processed"] == 2
        assert summary["published"] == 1  # Only one best item published per run
        
        # Verify db contents
        queue_items = pipeline.db.get_queue(status='published')
        assert len(queue_items) == 1
        assert queue_items[0]["title"] == "HackerNews Test Title"
        assert queue_items[0]["score"] == 95
        assert queue_items[0]["adapted_title"] == "Хайповый Заголовок"


@pytest.mark.asyncio
async def test_pipeline_moderation_flow():
    # Setup news items: one 95 (auto-publish), one 80 (moderation queue)
    mock_scraped = [
        NewsItem(source="hackernews", source_id="hn_95", title="HackerNews 95 Score", url="https://hn.com/95"),
        NewsItem(source="devto", source_id="dev_80", title="Devto 80 Score", url="https://dev.to/80")
    ]
    
    mock_adapted_res = {
        "title": "Хайповый Заголовок",
        "text": "Это адаптированный текст поста."
    }

    with patch("smm_engine.pipeline.run_all_scrapers", new_callable=AsyncMock) as mock_run_scrapers, \
         patch("smm_engine.pipeline.NewsScorer") as mock_scorer_class, \
         patch("smm_engine.pipeline.ContentAdapter") as mock_adapter_class, \
         patch("smm_engine.pipeline.TelegramPublisher") as mock_publisher_class, \
         patch("smm_engine.config.TELEGRAM_BOT_TOKEN", "mock_bot_token"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_httpx_post:
         
        mock_run_scrapers.return_value = mock_scraped
        
        mock_scorer_inst = MagicMock()
        mock_scorer_inst.score_item = AsyncMock(side_effect=lambda item: {
            "total": 95 if item.source == "hackernews" else 80,
            "reason": "Test reason"
        })
        mock_scorer_class.return_value = mock_scorer_inst
        
        mock_adapter_inst = MagicMock()
        mock_adapter_inst.adapt_news = AsyncMock(return_value=mock_adapted_res)
        mock_adapter_class.return_value = mock_adapter_inst
        
        mock_publisher_inst = MagicMock()
        mock_publisher_inst.publish_post_with_cover = AsyncMock(return_value=True)
        mock_publisher_inst._escape_html = MagicMock(side_effect=lambda x: str(x) if x else "")
        mock_publisher_inst._format_markdown_to_html = MagicMock(side_effect=lambda x: str(x) if x else "")
        mock_publisher_class.return_value = mock_publisher_inst
        
        # Setup mock admin_chat_id in database
        pipeline = SMMPipeline()
        pipeline.db.set_setting("admin_chat_id", "55555")
        
        mock_httpx_post.return_value = MagicMock(status_code=200)

        # Run pipeline
        summary = await pipeline.run()

        # Assert results
        assert summary["published"] == 1  # HackerNews 95 got auto-published
        assert summary["queued"] == 1     # Dev.to 80 got queued for moderation
        
        # Verify moderation notification was triggered
        # Check that httpx.AsyncClient.post was called to send the Telegram message to chat_id 55555
        called_chat_id_check = False
        for call in mock_httpx_post.call_args_list:
            json_payload = call[1].get("json", {})
            if json_payload.get("chat_id") == 55555:
                called_chat_id_check = True
                assert "ID: " in json_payload.get("text", "")
                assert "Devto 80" in json_payload.get("text", "")
                assert "80/100" in json_payload.get("text", "")
                
        assert called_chat_id_check, "Did not send Telegram moderation notification to admin"


@pytest.mark.asyncio
async def test_pipeline_records_primary_publish_before_optional_threads_failure():
    adapted = {"title": "Adapted", "text": "Adapted body"}

    with patch(
        "smm_engine.pipeline.run_all_scrapers",
        new=AsyncMock(return_value=[]),
    ), patch("smm_engine.pipeline.NewsScorer"), patch(
        "smm_engine.pipeline.ContentAdapter"
    ) as adapter_class, patch(
        "smm_engine.pipeline.TelegramPublisher"
    ) as telegram_class, patch(
        "smm_engine.pipeline.ThreadsPublisher"
    ) as threads_class:
        adapter_class.return_value.adapt_news = AsyncMock(return_value=adapted)
        telegram_class.return_value.publish_post_with_cover = AsyncMock(return_value=True)
        threads_class.return_value.publish_post = AsyncMock(
            side_effect=RuntimeError("optional channel unavailable")
        )

        pipeline = SMMPipeline()
        item_id = pipeline.db.save_news_item(
            "source",
            "primary-side-effect",
            "Original",
            "https://example.com/story",
            {},
        )
        pipeline.db.update_scoring(item_id, 100, "Excellent", status="parsed")

        summary = await pipeline.run()
        stored = pipeline.db.get_by_id(item_id)

    assert stored["status"] == "published"
    assert summary["published"] == 1


@pytest.mark.asyncio
async def test_production_moderation_notification_does_not_trust_legacy_admin(
    monkeypatch,
):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("TELEGRAM_ADMIN_CHAT_ID", raising=False)
    pipeline = SMMPipeline()
    pipeline.db.set_setting("admin_chat_id", "55555")

    with patch("smm_engine.config.TELEGRAM_BOT_TOKEN", "token"), patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
    ) as post:
        await pipeline._send_moderation_notification(
            1,
            "Title",
            80,
            "Reason",
            "Adapted",
            "Body",
            "source",
        )

    post.assert_not_awaited()
