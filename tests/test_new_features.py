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

# 6. Test AI Background Routing
@pytest.mark.asyncio
async def test_ai_background_routing():
    from smm_engine.media.image_handler import ImageGenerator
    
    gen = ImageGenerator()
    
    # Test that it falls back to Horde if HF fails
    with patch.object(gen, "generate_hf_background", return_value=None), \
         patch.object(gen, "generate_horde_background", return_value="fake_horde_path"):
        res = await gen.generate_ai_background("test")
        assert res == "fake_horde_path"
        
    # Test that it returns HF if successful
    with patch.object(gen, "generate_hf_background", return_value="fake_hf_path"), \
         patch.object(gen, "generate_horde_background", return_value="fake_horde_path"):
        res = await gen.generate_ai_background("test")
        assert res == "fake_hf_path"

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
    
    # Test double-escaped HTML formatting
    text = "&amp;lt;blockquote expandable&amp;gt;Double escaped text&amp;lt;/blockquote&amp;gt;"
    res = pub._format_markdown_to_html(text)
    assert "<blockquote expandable>" in res
    assert "</blockquote>" in res
    assert "&amp;" not in res

# 14. Test LoremFlickr URL Format with /any OR Search
@pytest.mark.anyio
async def test_loremflickr_url_format():
    from smm_engine.media.image_handler import ImageGenerator
    import httpx
    
    img_gen = ImageGenerator()
    original_get = httpx.AsyncClient.get
    
    requested_urls = []
    async def mock_get(self, url, *args, **kwargs):
        requested_urls.append(str(url))
        mock_resp = httpx.Response(200, content=b"fake_image_data")
        mock_resp.request = httpx.Request("GET", url)
        return mock_resp
        
    httpx.AsyncClient.get = mock_get
    try:
        await img_gen.fetch_background("artificial intelligence, glowing brain")
    finally:
        httpx.AsyncClient.get = original_get
        
    assert len(requested_urls) > 0
    url = requested_urls[0]
    assert "/all" in url or "/any" in url
    assert "artificial" in url
