import pytest
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from smm_engine.media.image_handler import ImageGenerator
from smm_engine.media.qr_code import QRCodeGenerator
from smm_engine.media.screenshot import ScreenshotGenerator

def test_image_generator_local(tmp_path):
    with patch("smm_engine.media.image_handler.BASE_DIR", tmp_path):
        img_gen = ImageGenerator()
        # Create a basic cover without background download (solid background fallback)
        output_path = img_gen.create_cover("Test News Headline: Gemini is Awesome!", bg_path=None)
        
        assert output_path is not None
        assert output_path.exists()
        assert output_path.suffix == ".jpg"

def test_image_generator_vertical(tmp_path):
    with patch("smm_engine.media.image_handler.BASE_DIR", tmp_path):
        img_gen = ImageGenerator()
        output_path = img_gen.create_cover("Vertical Reel hook text", bg_path=None, vertical=True)
        
        assert output_path is not None
        assert output_path.exists()
        assert "final_cover_v" in output_path.name

def test_image_generator_watermark(tmp_path):
    with patch("smm_engine.media.image_handler.BASE_DIR", tmp_path):
        img_gen = ImageGenerator()
        # Inject custom watermark to verify theme configuration loading
        img_gen.theme["watermark"] = {
            "font_size": 20,
            "text_parts": [
                {"text": "CustomWatermarkText", "color_type": "primary"},
                {"text": "⚡", "color_type": "accent"}
            ]
        }
        output_path = img_gen.create_cover("Watermark Test Cover Title", bg_path=None)
        
        assert output_path is not None
        assert output_path.exists()
        from PIL import Image
        img = Image.open(output_path)
        assert img.size == (1080, 1080)

@pytest.mark.asyncio
async def test_qr_code_generator(tmp_path):
    with patch("smm_engine.media.qr_code.BASE_DIR", tmp_path):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake_png_data"
        
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            qr_gen = QRCodeGenerator()
            qr_path = await qr_gen.generate_qr("https://t.me/test_channel")
            
            assert qr_path is not None
            assert qr_path.exists()
            with open(qr_path, "rb") as f:
                assert f.read() == b"fake_png_data"

@pytest.mark.asyncio
async def test_screenshot_generator(tmp_path):
    with patch("smm_engine.media.screenshot.BASE_DIR", tmp_path):
        # Mock responses for Microlink URL and Image download
        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200
        mock_api_resp.json.return_value = {"data": {"screenshot": {"url": "https://screenshot-image-bucket.s3.amazonaws.com/img.png"}}}
        
        mock_img_resp = MagicMock()
        mock_img_resp.status_code = 200
        mock_img_resp.content = b"fake_screenshot_data"
        
        async def mock_get(url, *args, **kwargs):
            if "microlink.io" in url:
                return mock_api_resp
            return mock_img_resp
            
        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            screen_gen = ScreenshotGenerator()
            screen_path = await screen_gen.capture_url("https://google.com")
            
            assert screen_path is not None
            assert screen_path.exists()
            with open(screen_path, "rb") as f:
                assert f.read() == b"fake_screenshot_data"

@pytest.mark.asyncio
async def test_engagement_generator():
    from smm_engine.content.engagement import EngagementGenerator
    
    mock_joke_resp = MagicMock()
    mock_joke_resp.status_code = 200
    mock_joke_resp.json.return_value = {"type": "single", "joke": "Why did the computer cold? It left its Windows open."}
    
    mock_gemini_resp = MagicMock()
    mock_gemini_resp.text = "Смешной перевод шутки про Windows."
    
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_gemini_resp
    
    with patch("httpx.AsyncClient.get", return_value=mock_joke_resp), \
         patch("google.generativeai.GenerativeModel", return_value=mock_model), \
         patch("smm_engine.content.engagement.GEMINI_API_KEY", "dummy_key"):
        eng_gen = EngagementGenerator()
        joke = await eng_gen.get_programming_joke()
        
        assert joke == "Смешной перевод шутки про Windows."
        mock_model.generate_content.assert_called_once()

@pytest.mark.asyncio
async def test_video_generator(tmp_path):
    from smm_engine.media.video_generator import VideoGenerator
    
    mock_storyboard = [
        {"caption": "Slide 1 Hook", "background_keywords": "neon"},
        {"caption": "Slide 2 Detail", "background_keywords": "matrix"}
    ]
    
    mock_gemini_resp = MagicMock()
    mock_gemini_resp.text = '[{"caption": "Slide 1 Hook", "background_keywords": "neon"}, {"caption": "Slide 2 Detail", "background_keywords": "matrix"}]'
    
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_gemini_resp
    
    from io import BytesIO
    from PIL import Image as PILImage
    img_io = BytesIO()
    PILImage.new("RGBA", (1, 1), (255, 0, 0, 255)).save(img_io, format="PNG")
    png_bytes = img_io.getvalue()
    
    mock_bg = MagicMock()
    mock_bg.status_code = 200
    mock_bg.content = png_bytes
    
    with patch("smm_engine.media.video_generator.BASE_DIR", tmp_path), \
         patch("smm_engine.media.image_handler.BASE_DIR", tmp_path), \
         patch("google.generativeai.GenerativeModel", return_value=mock_model), \
         patch("httpx.AsyncClient.get", return_value=mock_bg), \
         patch("smm_engine.media.video_generator.GEMINI_API_KEY", "dummy_key"):
        video_gen = VideoGenerator()
        
        # Mock the ffmpeg run to just return True
        video_gen._run_ffmpeg = MagicMock(return_value=True)
        
        # We need to write a dummy file where ffmpeg output is expected to mock success
        def mock_run_ffmpeg_side_effect(slide_paths, output_path):
            with open(output_path, "w") as f:
                f.write("mocked video content")
            return True
        video_gen._run_ffmpeg.side_effect = mock_run_ffmpeg_side_effect
        
        video_path = await video_gen.generate_reel("AI Released", "It is smart.")
        
        assert video_path is not None
        assert video_path.exists()
        assert video_path.name == "output_reel.mp4"


def test_image_generator_theme_color_formats(tmp_path):
    with patch("smm_engine.media.image_handler.BASE_DIR", tmp_path):
        img_gen = ImageGenerator()
        
        # Set custom theme colors with diverse formats (hex strings, tuples, lists, and empty/None values)
        img_gen.theme["colors"] = {
            "background_fallback": "#0d0f14",          # 6-char hex string
            "overlay_dim": "#0d0f1496",                # 8-char hex string with alpha
            "text_primary": (255, 255, 255),           # tuple (RGB)
            "brand_dark": [13, 15, 20, 255],           # list (RGBA)
            "brand_accent": (217, 4, 41, 255),         # tuple (RGBA)
            "watermark_text": None,                     # None value fallback
            "watermark_accent": ""                      # Empty string fallback
        }
        
        output_path = img_gen.create_cover("Test Color Formats Hex and Tuples", bg_path=None)
        
        assert output_path is not None
        assert output_path.exists()
        assert output_path.suffix == ".jpg"


