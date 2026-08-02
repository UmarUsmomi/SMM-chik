import pytest
import os
from io import BytesIO
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
async def test_concurrent_image_generators_use_isolated_download_paths(tmp_path):
    from PIL import Image as PILImage

    buffer = BytesIO()
    PILImage.new("RGB", (16, 16), color="navy").save(buffer, format="PNG")
    response = MagicMock(status_code=200, content=buffer.getvalue())

    with patch("smm_engine.media.image_handler.BASE_DIR", tmp_path), patch(
        "smm_engine.media.image_handler.fetch_public_http",
        new=AsyncMock(return_value=response),
    ):
        first_generator = ImageGenerator()
        second_generator = ImageGenerator()
        first_path = await first_generator.download_image("https://example.com/one.png")
        second_path = await second_generator.download_image("https://example.com/two.png")

    assert first_path is not None
    assert second_path is not None
    assert first_path != second_path
    assert first_path.exists()
    assert second_path.exists()


@pytest.mark.asyncio
async def test_download_image_rejects_excessive_pixel_dimensions(tmp_path):
    response = MagicMock(status_code=200, content=b"image-bytes")
    oversized_image = MagicMock()
    oversized_image.size = (100_000, 100_000)
    image_context = MagicMock()
    image_context.__enter__.return_value = oversized_image
    image_context.__exit__.return_value = False

    with patch("smm_engine.media.image_handler.BASE_DIR", tmp_path), patch(
        "smm_engine.media.image_handler.fetch_public_http",
        new=AsyncMock(return_value=response),
    ), patch("smm_engine.media.image_handler.Image.open", return_value=image_context):
        generator = ImageGenerator()
        path = await generator.download_image("https://example.com/oversized.png")

    assert path is None
    assert not list((tmp_path / "temp_media").glob("*_bg_downloaded.jpg"))

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


@pytest.mark.asyncio
async def test_image_generator_pollinations(tmp_path):
    with patch("smm_engine.media.image_handler.BASE_DIR", tmp_path):
        img_gen = ImageGenerator()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake_jpeg_image_data_with_sufficient_length_to_pass_validation_which_is_over_1000_bytes" * 20
        mock_response.headers = {"content-type": "image/jpeg"}
        
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            with patch("PIL.Image.open") as mock_image_open:
                mock_image_open.return_value.verify = MagicMock()
                path = await img_gen.generate_pollinations_background("test_keywords")
                assert path is not None
            assert path.exists()
            assert "bg_poll.jpg" in path.name


@pytest.mark.asyncio
async def test_image_generator_cloudflare(tmp_path):
    with patch("smm_engine.media.image_handler.BASE_DIR", tmp_path):
        # Test missing keys first (should return None)
        with patch("smm_engine.config.CLOUDFLARE_ACCOUNT_ID", None), \
             patch("smm_engine.config.CLOUDFLARE_API_TOKEN", None):
            img_gen = ImageGenerator()
            path = await img_gen.generate_cloudflare_background("test_keywords")
            assert path is None

        # Test with keys and successful mock call
        with patch("smm_engine.config.CLOUDFLARE_ACCOUNT_ID", "dummy_cf_account"), \
             patch("smm_engine.config.CLOUDFLARE_API_TOKEN", "dummy_cf_token"):
            img_gen = ImageGenerator()
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            # Generate a valid PNG image dynamically using PIL
            from io import BytesIO
            from PIL import Image as PILImage
            tmp_img = PILImage.new("RGB", (10, 10), color="blue")
            buf = BytesIO()
            tmp_img.save(buf, format="PNG")
            png_bytes = buf.getvalue()
            # Pad to exceed 1000 bytes (trailing bytes are ignored by PNG reader)
            mock_response.content = png_bytes + b'\x00' * 1000
            
            with patch("httpx.AsyncClient.post", return_value=mock_response):
                path = await img_gen.generate_cloudflare_background("test_keywords")
                assert path is not None
                assert path.exists()
                assert "bg_cf.png" in path.name


def test_image_generator_smart_crop(tmp_path):
    with patch("smm_engine.media.image_handler.BASE_DIR", tmp_path):
        from PIL import Image as PILImage
        img_gen = ImageGenerator()
        
        # Create a horizontal dummy image (800x400)
        width, height = 800, 400
        dummy_img = PILImage.new("RGB", (width, height), color="white")
        # Draw edges in the left half to verify edge-density-based cropping
        from PIL import ImageDraw
        draw = ImageDraw.Draw(dummy_img)
        for x in range(10, 300, 10):
            draw.line([(x, 10), (x, 390)], fill="black", width=2)
            
        target_w, target_h = 400, 400
        cropped = img_gen.smart_crop(dummy_img, target_w, target_h)
        
        assert cropped is not None
        assert cropped.size == (target_w, target_h)




