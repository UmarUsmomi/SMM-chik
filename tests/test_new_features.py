import pytest
import html
from unittest.mock import MagicMock, patch, AsyncMock
from smm_engine.publishers.telegram_pub import TelegramPublisher
from smm_engine.scrapers import run_all_scrapers
from smm_engine.scrapers.base import BaseScraper, NewsItem
from smm_engine.utils.gemini_helper import generate_content_with_retry
from google.api_core.exceptions import ResourceExhausted

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
    
    # Test custom blockquote expandable is preserved
    res = pub._format_markdown_to_html("Quote: <blockquote expandable>collapsible</blockquote>")
    assert "<blockquote expandable>collapsible</blockquote>" in res
    
    # Test double-escaped input (common AI output) is normalized and correctly unescaped
    res = pub._format_markdown_to_html("Escaped: &lt;blockquote expandable&gt;text&lt;/blockquote&gt;")
    assert "<blockquote expandable>text</blockquote>" in res
    
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

# 6. Test Pollinations AI background image generation
@pytest.mark.asyncio
async def test_pollinations_ai_bg_generation():
    from smm_engine.media.image_handler import ImageGenerator
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"fake_image_content"
    
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.return_value = mock_resp
    
    with patch("httpx.AsyncClient", return_value=mock_client):
        # Patch _setup_font to avoid any synchronous font downloads during tests
        with patch.object(ImageGenerator, "_setup_font", return_value=None):
            gen = ImageGenerator()
            res_path = await gen.generate_ai_background("test,keywords")
            
            assert res_path is not None
            assert "bg_ai.jpg" in str(res_path)
            mock_client.get.assert_called_once()
            assert "image.pollinations.ai" in mock_client.get.call_args[0][0]

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

# 8. Test Database clearing and bot reset command
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
            resp = client.post("/api/clear-db")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok", "message": "Database cleared"}
            assert len(db_mgr.get_recent_items()) == 0
            
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
            assert len(caption) <= 1024
            assert caption.endswith("...")
