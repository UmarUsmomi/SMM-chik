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
