import pytest
import html
from unittest.mock import MagicMock, patch, AsyncMock, ANY
from smm_engine.publishers.telegram_pub import TelegramPublisher
from smm_engine.scrapers import run_all_scrapers
from smm_engine.scrapers.base import BaseScraper, NewsItem
from smm_engine.utils.gemini_helper import generate_content_with_retry
from google.api_core.exceptions import ResourceExhausted


@pytest.mark.asyncio
async def test_telegram_publish_failure_does_not_log_provider_body(caplog):
    marker = "private-telegram-response-marker"
    response = MagicMock(status_code=400, text=marker)
    mocked_client = AsyncMock()
    mocked_client.post.return_value = response
    mocked_context = MagicMock()
    mocked_context.__aenter__ = AsyncMock(return_value=mocked_client)
    mocked_context.__aexit__ = AsyncMock(return_value=False)
    caplog.set_level("ERROR", logger="smm_engine.publishers.telegram_pub")

    with patch("smm_engine.publishers.telegram_pub.TELEGRAM_BOT_TOKEN", "token"), patch(
        "smm_engine.publishers.telegram_pub.TELEGRAM_CHANNEL_ID", "channel"
    ), patch("httpx.AsyncClient", return_value=mocked_context):
        publisher = TelegramPublisher()
        success = await publisher.publish_text("Title", "Text")

    assert success is False
    assert marker not in caplog.text


@pytest.mark.asyncio
async def test_telegram_publisher_fails_closed_when_production_credentials_are_missing(
    monkeypatch,
):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)

    with patch("smm_engine.publishers.telegram_pub.TELEGRAM_BOT_TOKEN", None), patch(
        "smm_engine.publishers.telegram_pub.TELEGRAM_CHANNEL_ID", None
    ):
        publisher = TelegramPublisher()

    assert await publisher.publish_text("Title", "Text") is False


# 1. Test HTML formatting & whitelisting in Telegram Publisher
def test_telegram_html_formatting_whitelist():
    pub = TelegramPublisher()
    
    # Test bold markdown conversion
    res = pub._format_markdown_to_html("This is **bold** text.")
    assert res == "This is <b>bold</b> text."
    
    # Test valid Telegram HTML tags are preserved
    res = pub._format_markdown_to_html("Hello <b>world</b>, this is <code>code</code>.")
    assert "<b>world</b>" in res
    assert "<code>code</code>" in res
    
    # Test blockquote tags are preserved (whitelisted)
    res = pub._format_markdown_to_html("Quote: <blockquote expandable>collapsible</blockquote>")
    assert "collapsible" in res
    assert "<blockquote expandable>" in res
    assert "</blockquote>" in res
    
    # Test double-escaped blockquote is unescaped and preserved
    res = pub._format_markdown_to_html("Escaped: &lt;blockquote expandable&gt;text&lt;/blockquote&gt;")
    assert "text" in res
    assert "<blockquote expandable>" in res
    assert "</blockquote>" in res
    
    # Test Markdown blockquote conversion (> prefix)
    res = pub._format_markdown_to_html("> This is a quote")
    assert "<blockquote expandable>" in res
    assert "This is a quote" in res
    assert "</blockquote>" in res
    
    # Test invalid HTML tags are escaped and rendered as safe text
    res = pub._format_markdown_to_html("Bad tag: <script>alert(1)</script>")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in res
    
    # Test special characters in normal text are escaped (to prevent Telegram parser errors)
    res = pub._format_markdown_to_html("A < B & B > C")
    assert "A &lt; B &amp; B &gt; C" in res
    
    # Test case-insensitivity of whitelisted tags
    res = pub._format_markdown_to_html("Hello <B>WORLD</B>")
    assert "Hello <b>WORLD</b>" in res or "Hello <B>WORLD</B>" in res

# 2. Test Gemini API Client retry and fallback logic
@pytest.mark.asyncio
async def test_gemini_fallback_logic():
    # We will mock genai.GenerativeModel
    # The first model ('model-A') will raise ResourceExhausted with daily quota error.
    # The second model ('gemini-3.1-flash-lite') will succeed.
    
    mock_model_1 = MagicMock()
    # Raise ResourceExhausted for daily limit
    mock_model_1.generate_content.side_effect = ResourceExhausted("daily quota exceeded for GenerateRequestsPerDay")
    
    mock_model_2 = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Success response"
    mock_model_2.generate_content.return_value = mock_response
    
    models_created = []
    
    def mock_generative_model(name):
        models_created.append(name)
        if name == "model-A":
            return mock_model_1
        elif name == "gemini-3.1-flash-lite":
            return mock_model_2
        # Fallback to model 2 for others to avoid errors
        return mock_model_2
        
    with patch("google.generativeai.GenerativeModel", side_effect=mock_generative_model), \
         patch("smm_engine.utils.gemini_helper.GEMINI_API_KEY", "dummy_key"):
         
        res = await generate_content_with_retry("hello", initial_model="model-A")
        
        assert res == "Success response"
        # Verify it attempted model-A and then fell back to gemini-3.1-flash-lite
        assert "model-A" in models_created
        assert "gemini-3.1-flash-lite" in models_created

# 3. Test dynamic plugin scraper loading
@pytest.mark.asyncio
async def test_dynamic_scraper_loading(tmp_path):
    # Create a dummy plugin scraper module in the plugins/scrapers directory
    plugins_dir = tmp_path / "plugins" / "scrapers"
    plugins_dir.mkdir(parents=True)
    
    plugin_code = """
from smm_engine.scrapers.base import BaseScraper, NewsItem

class DummyPluginScraper(BaseScraper):
    async def scrape(self):
        return [NewsItem(
            source="dummy_plugin",
            source_id="123",
            title="Plugin News Title",
            url="https://plugin-news.com",
            raw_data={}
        )]
"""
    plugin_file = plugins_dir / "dummy_plugin_scraper.py"
    with open(plugin_file, "w", encoding="utf-8") as f:
        f.write(plugin_code)
        
    # Patch Path to point plugins/scrapers to our temp directory
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.resolve", return_value=plugins_dir), \
         patch("pkgutil.iter_modules", return_value=[(None, "dummy_plugin_scraper", False)]):
         
         config = {
             "sources": {
                 # Enable dummy plugin scraper
                 "dummy_plugin_scraper": {"enabled": True},
                 # Disable other core scrapers to keep test fast and isolated
                 "hackernews": {"enabled": False},
                 "devto": {"enabled": False},
                 "steam": {"enabled": False},
                 "github": {"enabled": False},
                 "gamersnexus": {"enabled": False}
             }
         }
         
         # Run all scrapers and verify it ran the dynamic plugin scraper
         results = await run_all_scrapers(config)
         assert len(results) == 1
         assert results[0].source == "dummy_plugin"
         assert results[0].title == "Plugin News Title"

# 4. Test API logs endpoint
def test_api_logs():
    from fastapi.testclient import TestClient
    from bot.app import app
    client = TestClient(app)
    resp = client.get("/api/logs")
    assert resp.status_code == 200
    assert "logs" in resp.json()

# 5. Test dynamic theme loading
def test_dynamic_theme_loading():
    from smm_engine.media.image_handler import ImageGenerator
    
    with patch.object(ImageGenerator, "_setup_font", return_value=None):
        # Test Dracula theme loading
        with patch("smm_engine.config.BRANDING_THEME", "dracula"):
            gen = ImageGenerator()
            assert gen.theme.get("name") == "Dracula purple/pink theme"
            colors = gen.theme.get("colors", {})
            assert colors.get("brand_accent") == [255, 121, 198, 255]
            
        # Test Cyberpunk theme loading
        with patch("smm_engine.config.BRANDING_THEME", "cyberpunk"):
            gen = ImageGenerator()
            assert gen.theme.get("name") == "Cyberpunk neon theme"
            colors = gen.theme.get("colors", {})
            assert colors.get("brand_accent") == [252, 238, 10, 255]

# 6. Test AI Background Routing
@pytest.mark.asyncio
async def test_ai_background_routing():
    from smm_engine.media.image_handler import ImageGenerator
    
    gen = ImageGenerator()
    
    # 1. HuggingFace succeeds -> returns HF path
    with patch.object(gen, "generate_hf_background", return_value="fake_hf_path"), \
         patch.object(gen, "generate_pollinations_background", return_value="fake_poll_path"), \
         patch.object(gen, "generate_cloudflare_background", return_value="fake_cf_path"):
        res = await gen.generate_ai_background("test")
        assert res == "fake_hf_path"
        
    # 2. HF fails, Pollinations succeeds -> returns Pollinations path
    with patch.object(gen, "generate_hf_background", return_value=None), \
         patch.object(gen, "generate_pollinations_background", return_value="fake_poll_path"), \
         patch.object(gen, "generate_cloudflare_background", return_value="fake_cf_path"):
        res = await gen.generate_ai_background("test")
        assert res == "fake_poll_path"

    # 3. HF & Pollinations fail, Cloudflare succeeds -> returns Cloudflare path
    with patch.object(gen, "generate_hf_background", return_value=None), \
         patch.object(gen, "generate_pollinations_background", return_value=None), \
         patch.object(gen, "generate_cloudflare_background", return_value="fake_cf_path"):
        res = await gen.generate_ai_background("test")
        assert res == "fake_cf_path"

    # 4. All three fail -> returns procedural fallback path
    from PIL import Image
    fake_img = Image.new("RGBA", (10, 10))
    with patch.object(gen, "generate_hf_background", return_value=None), \
         patch.object(gen, "generate_pollinations_background", return_value=None), \
         patch.object(gen, "generate_cloudflare_background", return_value=None), \
         patch.object(gen, "_generate_procedural_background", return_value=fake_img):
        res = await gen.generate_ai_background("test")
        assert "procedural_fallback" in str(res)

# 7. Test Visual Prompt generation in TelegramPublisher
@pytest.mark.asyncio
async def test_telegram_publisher_visual_prompt():
    from smm_engine.publishers.telegram_pub import TelegramPublisher
    
    pub = TelegramPublisher()
    
    # Mock Gemini helper function
    mock_gemini_resp = "quantum computer, processor, laboratory"
    
    with patch("smm_engine.utils.gemini_helper.generate_content_with_retry", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = mock_gemini_resp
        
        # Patch config values
        with patch("smm_engine.publishers.telegram_pub.TELEGRAM_BOT_TOKEN", "dummy_token"), \
             patch("smm_engine.publishers.telegram_pub.TELEGRAM_CHANNEL_ID", "dummy_channel"):
             
             keywords = await pub._generate_visual_prompt("Title", "Body")
             assert keywords == "quantum computer, processor, laboratory"
             mock_generate.assert_called_once()

# 8. Test Database indexes, clearing, and bot reset command
def test_database_creates_indexes_for_dashboard_and_dedup_queries(tmp_path):
    import sqlite3

    from smm_engine.storage.database import DatabaseManager

    database_path = tmp_path / "indexed.db"
    with patch("smm_engine.storage.database.SQLITE_DB_PATH", str(database_path)):
        manager = DatabaseManager()
        manager.get_stats()
        manager.close_current()

    with sqlite3.connect(database_path) as connection:
        index_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }

    assert "idx_news_items_url" in index_names
    assert "idx_news_items_status_score_created" in index_names


def test_database_pipeline_lease_is_exclusive_and_recovers_after_expiry(tmp_path):
    import sqlite3

    from smm_engine.storage.database import DatabaseManager

    database_path = tmp_path / "leases.db"
    with patch("smm_engine.storage.database.SQLITE_DB_PATH", str(database_path)):
        first = DatabaseManager()
        assert first.acquire_lease("smm_pipeline", "first-owner", 60) is True
        first.close_current()

        second = DatabaseManager()
        assert second.acquire_lease("smm_pipeline", "second-owner", 60) is False
        assert second.release_lease("smm_pipeline", "second-owner") is False
        second.close_current()

        with sqlite3.connect(database_path) as connection:
            connection.execute(
                "UPDATE pipeline_leases SET locked_until = 0 WHERE name = ?",
                ("smm_pipeline",),
            )

        assert second.acquire_lease("smm_pipeline", "second-owner", 60) is True
        assert first.release_lease("smm_pipeline", "first-owner") is False
        assert second.release_lease("smm_pipeline", "second-owner") is True


def test_database_clear_and_reset_command(tmp_path):
    from smm_engine.storage.database import DatabaseManager
    from bot.app import app
    from fastapi.testclient import TestClient
    
    db_file = tmp_path / "test_clear.db"
    with patch("smm_engine.storage.database.SQLITE_DB_PATH", str(db_file)):
        # Initialize db and add an item
        db_mgr = DatabaseManager()
        item_id = db_mgr.save_news_item("test_src", "id_1", "Title 1", "https://url.com/1", {})
        
        # Verify item exists
        assert len(db_mgr.get_recent_items()) == 1
        
        # Clear database and verify empty
        db_mgr.clear_all_news()
        assert len(db_mgr.get_recent_items()) == 0
        
        # Re-save item and test API endpoint
        db_mgr.save_news_item("test_src", "id_1", "Title 1", "https://url.com/1", {})
        assert len(db_mgr.get_recent_items()) == 1
        
        # Test endpoint with FastAPI TestClient
        with patch("bot.app.db", db_mgr):
            client = TestClient(app)
            resp = client.post("/api/clear-db", json={"confirmed": True})
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok", "message": "Database cleared"}
            assert len(db_mgr.get_recent_items()) == 0

            db_mgr.save_news_item("test_src", "id_2", "Title 2", "https://url.com/2", {})
            resp = client.post("/api/clear-db")
            assert resp.status_code == 422
            assert len(db_mgr.get_recent_items()) == 1
            db_mgr.clear_all_news()

            # Test Telegram Bot webhook reset command
            db_mgr.save_news_item("test_src", "id_1", "Title 1", "https://url.com/1", {})
            assert len(db_mgr.get_recent_items()) == 1
            
            # Mock sending message
            with patch("bot.app.send_bot_message", new_callable=AsyncMock) as mock_send:
                payload = {
                    "update_id": 2000,
                    "message": {
                        "message_id": 10,
                        "chat": {"id": 12345, "type": "private"},
                        "text": "/reset"
                    }
                }
                resp = client.post("/webhook", json=payload)
                assert resp.status_code == 200
                mock_send.assert_called_once()
                assert "подтвержд" in mock_send.call_args[0][1].lower()
                assert len(db_mgr.get_recent_items()) == 1

                mock_send.reset_mock()
                payload["update_id"] = 2001
                payload["message"]["text"] = "/reset CONFIRM"
                resp = client.post("/webhook", json=payload)
                assert resp.status_code == 200
                mock_send.assert_called_once()
                assert "База данных новостей очищена" in mock_send.call_args[0][1]
                assert len(db_mgr.get_recent_items()) == 0

# 9. Test Caption Truncation when long text is sent
@pytest.mark.asyncio
async def test_telegram_publisher_caption_split():
    from unittest.mock import mock_open
    from smm_engine.publishers.telegram_pub import TelegramPublisher
    pub = TelegramPublisher()
    pub.enabled = True
    pub.bot_token = "dummy_token"
    pub.channel_id = "dummy_channel"
    
    # Create text that will exceed 1024 characters
    long_text = "A" * 1200
    
    # Mock httpx.AsyncClient.post
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.post.return_value = mock_response
    
    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch("builtins.open", mock_open(read_data=b"fake_image")):
            success = await pub.publish_photo("Short Title", long_text, "fake_path.jpg")
            
            assert success is True
            # Expect only 1 call to sendPhoto with truncated caption
            assert mock_client.post.call_count == 1
            
            args_photo = mock_client.post.call_args_list[0]
            assert "sendPhoto" in args_photo[0][0]
            caption = args_photo[1]["data"]["caption"]
            assert "Short Title" in caption
            assert pub._telegram_text_length(caption) <= 1024
            assert caption.endswith("...")


@pytest.mark.asyncio
async def test_telegram_publisher_keeps_quote_when_caption_is_truncated():
    from unittest.mock import mock_open

    pub = TelegramPublisher()
    pub.enabled = True
    pub.bot_token = "dummy_token"
    pub.channel_id = "dummy_channel"
    quote = "A quoted statement that must remain visible in the published post."
    long_text = (
        "Introductory detail. " * 90
        + f"<blockquote expandable>{quote}</blockquote>"
        + "\nClosing context. " * 30
    )

    mock_response = MagicMock(status_code=200)
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_client), \
         patch("builtins.open", mock_open(read_data=b"fake_image")):
        assert await pub.publish_photo("Short Title", long_text, "fake_path.jpg")

    caption = mock_client.post.call_args.kwargs["data"]["caption"]
    assert f"<blockquote expandable>{quote}</blockquote>" in caption
    assert pub._telegram_text_length(caption) <= 1024


@pytest.mark.asyncio
async def test_content_adapter_restores_quote_when_humanizer_drops_placeholder():
    from smm_engine.content.adapter import ContentAdapter

    adapter = ContentAdapter()
    adapter.enabled = True
    quote = "<blockquote expandable>Original quoted statement.</blockquote>"
    item = NewsItem(
        source="test_source",
        source_id="quoted-item",
        title="Quoted Title",
        url="https://example.com/quoted",
        raw_data={"tags": []},
    )

    with patch.object(
        adapter,
        "_adapt_pass",
        new=AsyncMock(return_value={"title": "Title", "body": f"Intro. {quote}"}),
    ), patch.object(
        adapter.humanizer,
        "humanize",
        new=AsyncMock(side_effect=["Title", "Edited intro without placeholder."]),
    ):
        adapted = await adapter.adapt_news(item)

    assert adapted is not None
    assert quote in adapted["text"]

# 10. Test HTML-aware truncation
def test_telegram_publisher_html_aware_truncation():
    from smm_engine.publishers.telegram_pub import TelegramPublisher
    pub = TelegramPublisher()
    
    # Test simple truncation
    # "Hello world how are you" has length 23.
    # With max_raw_len = 10, it should fit "Hello w" (7 chars) + "..." (3 chars) = 10 chars.
    res = pub._truncate_html("Hello world how are you", 10)
    assert res == "Hello w..."
    assert len(res) <= 10
    
    # Test simple truncation with word boundary
    # "Hello world how are you", max_raw_len = 16
    # "Hello world h" is 13 chars + "..." = 16 chars.
    res_wb = pub._truncate_html("Hello world how are you", 16)
    assert res_wb == "Hello world h..."
    assert len(res_wb) <= 16
    
    # Test truncation with HTML tags
    # "Hello <b>world</b> how are you"
    # To fit "Hello <b>world...</b>" we need:
    # "Hello " (6) + "<b>" (3) + "world" (5) + "..." (3) + "</b>" (4) = 21 chars.
    # If we pass max_raw_len = 18, it must truncate further to fit within 18 chars:
    # "Hello " (6) + "<b>" (3) + "wo" (2) + "..." (3) + "</b>" (4) = 18 chars.
    res = pub._truncate_html("Hello <b>world</b> how are you", 18)
    assert res == "Hello <b>wo...</b>"
    assert len(res) <= 18
    
    # If we pass max_raw_len = 17, it should truncate to fit within 17:
    # "Hello " (6) + "<b>" (3) + "w" (1) + "..." (3) + "</b>" (4) = 17 chars.
    res_trunc = pub._truncate_html("Hello <b>world</b> how are you", 17)
    assert res_trunc == "Hello <b>w...</b>"
    assert len(res_trunc) <= 17
    
    # Test multiple nested tags
    # "<blockquote expandable>Hello <b>world</b>!</blockquote>"
    # Let's check length:
    # "<blockquote expandable>" (23) + "Hello <b>world</b>!" (19) + "</blockquote>" (13) = 55 chars.
    # To fit "<blockquote expandable>Hello <b>w...</b></blockquote>" we need:
    # "<blockquote expandable>" (23) + "Hello " (6) + "<b>" (3) + "w" (1) + "..." (3) + "</b>" (4) + "</blockquote>" (13) = 53 chars.
    res_nested = pub._truncate_html("<blockquote expandable>Hello <b>world</b>!</blockquote>", 53)
    assert res_nested == "<blockquote expandable>Hello <b>w...</b></blockquote>"
    assert len(res_nested) <= 53

# 11. Test List Formatting in Telegram Publisher
def test_telegram_publisher_list_formatting():
    from smm_engine.publishers.telegram_pub import TelegramPublisher
    pub = TelegramPublisher()
    
    # Test ul list tag replacement
    text = "<ul><li>First item</li><li>Second item</li></ul>"
    res = pub._format_markdown_to_html(text)
    assert "▫️ First item" in res
    assert "▫️ Second item" in res
    assert "<ul>" not in res
    assert "<li>" not in res
    
    # Test paragraph and br tag replacements
    text2 = "<p>Paragraph 1</p><br/>Paragraph 2"
    res2 = pub._format_markdown_to_html(text2)
    assert "Paragraph 1" in res2
    assert "Paragraph 2" in res2
    assert "<p>" not in res2
    assert "<br/>" not in res2

# 12. Test Robust JSON Parsing
def test_robust_json_parsing():
    from smm_engine.utils.gemini_helper import parse_json_robust
    
    # Standard JSON
    assert parse_json_robust('{"key": "value"}') == {"key": "value"}
    
    # Markdown-wrapped JSON
    assert parse_json_robust('```json\n{"key": "value"}\n```') == {"key": "value"}
    
    # JSON with leading/trailing stray text
    assert parse_json_robust('Here is the JSON: {"key": "value"} Hope you like it!') == {"key": "value"}

# 13. Test Double HTML Unescaping
def test_telegram_publisher_double_unescaping():
    from smm_engine.publishers.telegram_pub import TelegramPublisher
    pub = TelegramPublisher()
    
    # Test double-escaped HTML formatting with blockquote (should be preserved)
    text = "&amp;lt;blockquote expandable&amp;gt;Double escaped text&amp;lt;/blockquote&amp;gt;"
    res = pub._format_markdown_to_html(text)
    assert "Double escaped text" in res
    assert "<blockquote expandable>" in res
    assert "&amp;" not in res

# 14. Test Publish Original Image Bypass logic (R3)
@pytest.mark.asyncio
async def test_telegram_publisher_original_image_bypass():
    from smm_engine.publishers.telegram_pub import TelegramPublisher
    from smm_engine.media.image_handler import ImageGenerator
    from pathlib import Path
    
    pub = TelegramPublisher()
    pub.enabled = True
    pub.bot_token = "dummy_token"
    pub.channel_id = "dummy_channel"
    
    # Mock download_image to return a path that exists
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    
    mock_cover_path = MagicMock(spec=Path)
    mock_cover_path.exists.return_value = True
    
    with patch.object(ImageGenerator, "download_image", return_value=mock_path) as mock_download, \
         patch.object(ImageGenerator, "create_cover", return_value=mock_cover_path) as mock_create_cover, \
         patch.object(pub, "publish_photo", return_value=True) as mock_publish_photo, \
         patch.object(pub, "_generate_cover_title", side_effect=lambda t, txt: t) as mock_cover_title:
         
        raw_data = {"cover_image": "http://example.com/image.jpg"}
        res = await pub.publish_post_with_cover("Test Title", "Test Text", raw_data=raw_data)
        
        assert res is True
        mock_download.assert_called_once_with("http://example.com/image.jpg")
        # create_cover should be called to apply overlay
        mock_create_cover.assert_called_once_with("Test Title", mock_path)
        # publish_photo should be called with cover path
        mock_publish_photo.assert_called_once_with("Test Title", "Test Text", str(mock_cover_path))
        # Ensure both cover and bg are unlinked
        mock_cover_path.unlink.assert_called_once()
        mock_path.unlink.assert_called_once()

    # Test fallback to AI background generation when download fails
    mock_ai_path = MagicMock(spec=Path)
    mock_ai_path.exists.return_value = True
    mock_cover_path = MagicMock(spec=Path)
    mock_cover_path.exists.return_value = True

    with patch.object(ImageGenerator, "download_image", return_value=None) as mock_download, \
         patch.object(ImageGenerator, "generate_ai_background", return_value=mock_ai_path) as mock_gen_ai, \
         patch.object(ImageGenerator, "create_cover", return_value=mock_cover_path) as mock_create_cover, \
         patch.object(pub, "publish_photo", return_value=True) as mock_publish_photo, \
         patch.object(pub, "_generate_visual_prompt", return_value="visual prompt") as mock_vis, \
         patch.object(pub, "_generate_cover_title", side_effect=lambda t, txt: t) as mock_cover_title:
         
        raw_data = {"cover_image": "http://example.com/image.jpg"}
        res = await pub.publish_post_with_cover("Test Title", "Test Text", raw_data=raw_data)
        
        assert res is True
        mock_download.assert_called_once_with("http://example.com/image.jpg")
        mock_gen_ai.assert_called_with("visual prompt")
        # create_cover should be called since is_original_image is False
        mock_create_cover.assert_called_once_with("Test Title", mock_ai_path)
        # publish_photo should be called with mock_cover_path
        mock_publish_photo.assert_called_once_with("Test Title", "Test Text", str(mock_cover_path))
        # Ensure both cover and bg are deleted
        mock_cover_path.unlink.assert_called_once()
        mock_ai_path.unlink.assert_called_once()


# 15. Test Selective Blockquote Logic (R6)
@pytest.mark.asyncio
async def test_selective_blockquote():
    from smm_engine.content.adapter import ContentAdapter
    from smm_engine.scrapers.base import NewsItem
    import random
    
    adapter = ContentAdapter()
    
    # Mock generate_content_with_retry so it doesn't call actual Gemini API
    with patch("smm_engine.content.adapter.generate_content_with_retry", new_callable=AsyncMock) as mock_generate, \
         patch("smm_engine.content.adapter.parse_json_robust") as mock_parse:
        
        mock_generate.return_value = "{}"
        mock_parse.return_value = {"title": "Test Title", "body": "Test Body"}
        
        # Scenario 1: Short content (< 500 chars)
        short_content = "This is a short news content."
        item_short = NewsItem(
            source="test_source",
            source_id="1",
            title="Short Title",
            url="http://example.com/short",
            raw_data={"content": short_content}
        )
        
        # Should always prohibit blockquotes
        await adapter._adapt_pass(item_short)
        
        prompt_short = mock_generate.call_args[0][0]
        assert "КАТЕГОРИЧЕСКИ ЗАПРЕЩАЕТСЯ использовать тег <blockquote>" in prompt_short
        assert "Если в новости есть яркая прямая цитата" not in prompt_short

        # Scenario 2: Long content (> 500 chars) with random < 0.60
        long_content = "A" * 600
        item_long = NewsItem(
            source="test_source",
            source_id="2",
            title="Long Title",
            url="http://example.com/long",
            raw_data={"content": long_content}
        )
        
        mock_generate.reset_mock()
        with patch("random.random", return_value=0.50):
            await adapter._adapt_pass(item_long)
            
        prompt_long_allowed = mock_generate.call_args[0][0]
        assert "Если в новости есть яркая прямая цитата" in prompt_long_allowed
        assert "КАТЕГОРИЧЕСКИ ЗАПРЕЩАЕТСЯ использовать тег <blockquote>" not in prompt_long_allowed

        # Scenario 3: Long content (> 500 chars) with random >= 0.60
        mock_generate.reset_mock()
        with patch("random.random", return_value=0.70):
            await adapter._adapt_pass(item_long)
            
        prompt_long_forbidden = mock_generate.call_args[0][0]
        assert "КАТЕГОРИЧЕСКИ ЗАПРЕЩАЕТСЯ использовать тег <blockquote>" in prompt_long_forbidden
        assert "Если в новости есть яркая прямая цитата" not in prompt_long_forbidden


# 16. Test Scheduler Loop Timing (R7)
@pytest.mark.asyncio
async def test_scheduler_loop_timing():
    from bot.app import scheduler_loop
    from datetime import datetime, timezone
    import asyncio
    
    mock_get_setting = MagicMock()
    mock_set_setting = MagicMock()
    mock_run_pipeline = AsyncMock()
    mock_sleep = AsyncMock()
    
    sleep_count = 0
    def side_effect_sleep(secs):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count > 3: # prevent infinite loop
            raise asyncio.CancelledError()
        return None
    
    mock_sleep.side_effect = side_effect_sleep
    
    interval_seconds = 10800
    
    # Scenario A: first run, no last run in DB
    db_state = {}
    mock_get_setting.side_effect = lambda key: db_state.get(key)
    mock_set_setting.side_effect = lambda key, val: db_state.update({key: val})
    
    with patch("bot.app.db.get_setting", mock_get_setting), \
         patch("bot.app.db.set_setting", mock_set_setting), \
         patch("bot.app.run_pipeline_task", mock_run_pipeline), \
         patch("asyncio.sleep", mock_sleep), \
         patch("os.getenv", return_value="3.0"):
         
        try:
            await scheduler_loop()
        except asyncio.CancelledError:
            pass
            
        assert mock_sleep.call_args_list[0][0][0] == 30
        mock_set_setting.assert_any_call("last_pipeline_run", ANY)
        mock_run_pipeline.assert_called_once()
        assert mock_sleep.call_args_list[1][0][0] == interval_seconds

    # Scenario B: elapsed time is less than interval
    last_run_time = datetime.now(timezone.utc).timestamp() - 3600
    last_run_iso = datetime.fromtimestamp(last_run_time, tz=timezone.utc).isoformat()
    
    mock_get_setting = MagicMock(return_value=last_run_iso)
    mock_set_setting = MagicMock()
    mock_run_pipeline = AsyncMock()
    mock_sleep = AsyncMock()
    sleep_count = 0
    mock_sleep.side_effect = side_effect_sleep
    
    with patch("bot.app.db.get_setting", mock_get_setting), \
         patch("bot.app.db.set_setting", mock_set_setting), \
         patch("bot.app.run_pipeline_task", mock_run_pipeline), \
         patch("asyncio.sleep", mock_sleep), \
         patch("os.getenv", return_value="3.0"):
         
        try:
            await scheduler_loop()
        except asyncio.CancelledError:
            pass
            
        assert mock_sleep.call_args_list[0][0][0] == 30
        remaining_sleep = mock_sleep.call_args_list[1][0][0]
        assert abs(remaining_sleep - 7200) < 5
        mock_run_pipeline.assert_not_called()
