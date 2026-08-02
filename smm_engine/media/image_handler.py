import httpx
import logging
import yaml
import asyncio
import re
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import Optional, Any
from uuid import uuid4
from smm_engine.config import BASE_DIR
from smm_engine.utils.network import fetch_public_http

logger = logging.getLogger(__name__)

MAX_DOWNLOADED_IMAGE_PIXELS = 40_000_000

class ImageGenerator:
    def __init__(self):
        self.temp_dir = BASE_DIR / "temp_media"
        self.temp_dir.mkdir(exist_ok=True)
        self.artifact_prefix = uuid4().hex
        # Choose a basic font path or download one
        self.font_path = self._setup_font()
        # Load active theme configuration
        self.theme = self._load_theme()

    def _temp_path(self, filename: str) -> Path:
        """Return a task-isolated path so concurrent publications cannot collide."""
        return self.temp_dir / f"{self.artifact_prefix}_{filename}"

    def _parse_color(self, color_val: Any, default: list) -> list:
        """Parses color value from theme configuration (supporting list, tuple, and hex strings) into an RGBA list of 4 integers."""
        if not color_val:
            return default
        if isinstance(color_val, (list, tuple)):
            val = list(color_val)
            if len(val) < 4:
                val = val + [255] * (4 - len(val))
            return val[:4]
        if isinstance(color_val, str):
            color_str = color_val.strip()
            if color_str.startswith("#"):
                hex_val = color_str.lstrip("#")
                if len(hex_val) == 6:
                    r = int(hex_val[0:2], 16)
                    g = int(hex_val[2:4], 16)
                    b = int(hex_val[4:6], 16)
                    return [r, g, b, 255]
                elif len(hex_val) == 8:
                    r = int(hex_val[0:2], 16)
                    g = int(hex_val[2:4], 16)
                    b = int(hex_val[4:6], 16)
                    a = int(hex_val[6:8], 16)
                    return [r, g, b, a]
        return default

    def _setup_font(self) -> Path:
        """Returns the path to a Cyrillic-capable font with robust fallback chain."""
        # 1. Try bundled fonts (RussoOne, Montserrat)
        candidates = [
            Path(__file__).resolve().parent.parent.parent / "fonts" / "RussoOne-Regular.ttf",
            Path(__file__).resolve().parent.parent.parent / "fonts" / "Montserrat-Bold.ttf",
            Path(__file__).resolve().parent.parent.parent / "fonts" / "Montserrat-Regular.ttf",
        ]
        for font_file in candidates:
            if font_file.exists():
                try:
                    test_font = ImageFont.truetype(str(font_file), 42)
                    test_font.getlength("Привет")
                    logger.info(f"Using bundled font: {font_file}")
                    return font_file
                except Exception as e:
                    logger.warning(f"Bundled font {font_file} exists but failed validation: {e}")
                    continue

        # 2. Try common system fonts across platforms
        system_fonts = [
            Path("C:/Windows/Fonts/arialbd.ttf"),
            Path("C:/Windows/Fonts/Arial.ttf"),
            Path("C:/Windows/Fonts/segoeuib.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
            Path("/System/Library/Fonts/Helvetica.ttc"),
            Path("/Library/Fonts/Arial Bold.ttf"),
        ]
        for font_file in system_fonts:
            if font_file.exists():
                try:
                    test_font = ImageFont.truetype(str(font_file), 42)
                    test_font.getlength("Привет")
                    logger.info(f"Using system font: {font_file}")
                    return font_file
                except Exception:
                    continue

        # 3. Download Roboto-Bold from Google Fonts as ultimate fallback
        temp_font = self.temp_dir / "Roboto-Bold.ttf"
        if not temp_font.exists():
            try:
                logger.info("Downloading Roboto-Bold font (Cyrillic fallback)...")
                url = "https://github.com/google/fonts/raw/main/ofl/roboto/Roboto-Bold.ttf"
                resp = httpx.get(url, timeout=15)
                if resp.status_code == 200 and len(resp.content) > 10000:
                    with open(temp_font, "wb") as f:
                        f.write(resp.content)
                    logger.info(f"Downloaded Roboto-Bold to {temp_font}")
                else:
                    logger.warning(f"Failed to download Roboto-Bold: {resp.status_code}")
            except Exception as e:
                logger.error(f"Error downloading Roboto-Bold: {e}")

        if temp_font.exists():
            try:
                test_font = ImageFont.truetype(str(temp_font), 42)
                test_font.getlength("Привет")
                return temp_font
            except Exception as e:
                logger.warning(f"Downloaded Roboto-Bold failed validation: {e}")

        return None

    def _load_theme(self) -> dict:
        """Loads branding theme configuration from themes directory"""
        from smm_engine.config import BRANDING_THEME
        theme_path = BASE_DIR / "themes" / f"{BRANDING_THEME}.yaml"
        if theme_path.exists():
            try:
                with open(theme_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data:
                        logger.info(f"Loaded branding theme: {data.get('name', 'Unnamed')}")
                        return data
            except Exception as e:
                logger.error(f"Failed to load theme from {theme_path}: {e}")
        
        # Hardcoded fallback theme matching the structure of default.yaml
        logger.info("Using hardcoded fallback branding theme.")
        return {
            "colors": {
                "background_fallback": [13, 15, 20, 255],
                "overlay_dim": [13, 15, 20, 150],
                "text_primary": [255, 255, 255, 255],
                "brand_dark": [13, 15, 20, 255],
                "brand_accent": [217, 4, 41, 255],
                "splatter_dark": [255, 255, 255, 180],
                "splatter_accent": [217, 4, 41, 180],
                "watermark_text": [255, 255, 255, 255],
                "watermark_accent": [217, 4, 41, 255]
            },
            "layout": {
                "font_size_square": 56,
                "font_size_vertical": 42,
                "wrap_width_square": 900,
                "wrap_width_vertical": 600,
                "padding_left_square": 90,
                "padding_left_vertical": 60
            },
            "watermark": {
                "font_size": 24,
                "text_parts": [
                    {"text": "/ игры ", "color_type": "primary"},
                    {"text": "⚡", "color_type": "accent"},
                    {"text": " патчи /", "color_type": "primary"}
                ]
            }
        }


    async def generate_hf_background(self, keywords: str, vertical: bool = False, retries: int = 2) -> Path:
        """Generates background using Hugging Face Serverless Inference API with retry."""
        from smm_engine.config import HUGGINGFACE_API_KEY
        if not HUGGINGFACE_API_KEY:
            return None
            
        img_path = self._temp_path("bg_hf_v.jpg" if vertical else "bg_hf.jpg")
        width, height = (720, 1280) if vertical else (1080, 1080)
        clean_keywords = keywords.replace(",", " ")
        prompt = (
            f"A dark, high-contrast techno-gaming background featuring {clean_keywords}. "
            "The composition is vertically split: the upper half contains glowing cyberpunk neon accents, "
            "digital HUD wireframes, and intricate circuit lines in electric cyan and vibrant red. "
            "The lower half is a clean, dark negative space with deep black shadows and minimal gradients. "
            "Futuristic gaming aesthetic, clean digital render, synthwave mood, dramatic atmospheric lighting, "
            "sharp details in the upper section, 8k resolution. No text, letters, or watermark."
        )
        
        api_url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
        headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
        payload = {"inputs": prompt}
        
        for attempt in range(retries + 1):
            logger.info(f"Generating AI cover using Hugging Face (attempt {attempt + 1}): {prompt[:60]}...")
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(api_url, headers=headers, json=payload, timeout=120)
                    if resp.status_code == 200:
                        content_type = resp.headers.get("content-type", "").lower()
                        if "image" in content_type or "octet-stream" in content_type or len(resp.content) > 10000:
                            with open(img_path, "wb") as f:
                                f.write(resp.content)
                            try:
                                test_img = Image.open(img_path)
                                test_img.verify()
                                logger.info("Hugging Face image validated successfully")
                                return img_path
                            except Exception as e:
                                logger.warning(f"Hugging Face returned invalid image: {e}")
                        else:
                            logger.warning(f"Hugging Face returned non-image response: content-type={content_type}, body={resp.text[:200]}")
                    elif resp.status_code == 503:
                        logger.warning(f"Hugging Face model is loading (503), retrying...")
                    else:
                        logger.warning(f"Hugging Face API failed: {resp.status_code} {resp.text[:200]}")
            except Exception as e:
                logger.error(f"Error calling Hugging Face API (attempt {attempt + 1}): {e}")
            if attempt < retries:
                await asyncio.sleep(5 * (attempt + 1))
        return None

    async def generate_pollinations_background(self, keywords: str, vertical: bool = False, retries: int = 2) -> Path:
        """Generates background using Pollinations.ai — fully free, no API key needed.
        Uses a simple GET request with the prompt encoded in the URL."""
        import urllib.parse
        
        img_path = self._temp_path("bg_poll_v.jpg" if vertical else "bg_poll.jpg")
        width, height = (720, 1280) if vertical else (1080, 1080)
        
        clean_keywords = keywords.replace(",", " ")
        prompt = (
            f"dark high-contrast techno-gaming background featuring {clean_keywords}, "
            "cyberpunk neon accents, digital HUD wireframes, circuit lines in electric cyan "
            "and vibrant red, deep black shadows, futuristic gaming aesthetic, synthwave mood, "
            "dramatic atmospheric lighting, 8k resolution, no text no letters no watermark"
        )
        
        encoded_prompt = urllib.parse.quote(prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width={width}&height={height}&nologo=true&seed={abs(hash(keywords)) % 100000}&enhance=true"
        )
        
        for attempt in range(retries + 1):
            logger.info(f"Generating AI cover using Pollinations.ai (attempt {attempt + 1}): {prompt[:60]}...")
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=60, follow_redirects=True)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        # Check content-type to avoid HTML error pages
                        content_type = resp.headers.get("content-type", "").lower()
                        if "image" in content_type or "octet-stream" in content_type:
                            with open(img_path, "wb") as f:
                                f.write(resp.content)
                            try:
                                test_img = Image.open(img_path)
                                test_img.verify()
                                logger.info("Successfully generated background via Pollinations.ai")
                                return img_path
                            except Exception as e:
                                logger.warning(f"Pollinations.ai returned invalid image: {e}")
                        else:
                            logger.warning(f"Pollinations.ai returned non-image content-type: {content_type}")
                    else:
                        logger.warning(f"Pollinations.ai failed: status={resp.status_code}, size={len(resp.content)}")
            except Exception as e:
                logger.error(f"Error calling Pollinations.ai (attempt {attempt + 1}): {e}")
            if attempt < retries:
                await asyncio.sleep(3 * (attempt + 1))
        return None

    async def generate_cloudflare_background(self, keywords: str, vertical: bool = False) -> Path:
        """Generates background using Cloudflare Workers AI REST API."""
        from smm_engine.config import CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN
        if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
            return None
        
        img_path = self._temp_path("bg_cf_v.png" if vertical else "bg_cf.png")
        
        clean_keywords = keywords.replace(",", " ")
        prompt = (
            f"A dark, high-contrast techno-gaming background featuring {clean_keywords}. "
            "Cyberpunk neon accents in electric cyan and vibrant red, digital HUD wireframes, "
            "glowing circuit lines, deep black shadows in lower half, futuristic gaming aesthetic, "
            "synthwave mood, dramatic atmospheric lighting, sharp details, 8k resolution. "
            "No text, letters, or watermark."
        )
        
        api_url = (
            f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}"
            "/ai/run/@cf/black-forest-labs/flux-1-schnell"
        )
        headers = {
            "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {"prompt": prompt}
        
        logger.info(f"Generating AI cover using Cloudflare Workers AI: {prompt[:60]}...")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(api_url, headers=headers, json=payload, timeout=45)
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "")
                    if "image" in content_type:
                        # Direct image bytes
                        with open(img_path, "wb") as f:
                            f.write(resp.content)
                    elif "json" in content_type:
                        # JSON response with base64 image
                        import json, base64
                        data = resp.json()
                        if isinstance(data, dict) and "result" in data:
                            result = data["result"]
                            if isinstance(result, dict) and "image" in result:
                                img_bytes = base64.b64decode(result["image"])
                                with open(img_path, "wb") as f:
                                    f.write(img_bytes)
                            else:
                                logger.warning(f"Cloudflare unexpected result structure: {list(data.keys())}")
                                return None
                        else:
                            logger.warning(f"Cloudflare unexpected response: {str(data)[:200]}")
                            return None
                    else:
                        # Try saving as-is (could be raw image bytes without proper content-type)
                        if len(resp.content) > 1000:
                            with open(img_path, "wb") as f:
                                f.write(resp.content)
                        else:
                            logger.warning(f"Cloudflare response too small: {len(resp.content)} bytes")
                            return None
                    
                    # Validate the saved file is actually an image
                    try:
                        test_img = Image.open(img_path)
                        test_img.verify()
                        logger.info("Successfully generated background via Cloudflare Workers AI")
                        return img_path
                    except Exception as e:
                        logger.warning(f"Cloudflare output is not a valid image: {e}")
                        img_path.unlink(missing_ok=True)
                        return None
                else:
                    logger.warning(f"Cloudflare Workers AI failed: status={resp.status_code}, body={resp.text[:200]}")
        except Exception as e:
            logger.error(f"Error calling Cloudflare Workers AI: {e}")
        return None

    async def generate_ai_background(self, keywords: str = "technology,gaming", vertical: bool = False) -> Path:
        """Routes between AI image providers with graceful fallback chain:
        HuggingFace → Pollinations.ai → Cloudflare Workers AI.
        Falls back to procedural gradient if all generators fail."""
        # 1. Try HuggingFace (requires API key)
        hf_path = await self.generate_hf_background(keywords, vertical)
        if hf_path:
            return hf_path
        
        # 2. Try Pollinations.ai (free, no key needed)
        logger.info("Falling back to Pollinations.ai for image generation...")
        poll_path = await self.generate_pollinations_background(keywords, vertical)
        if poll_path:
            return poll_path
        
        # 3. Try Cloudflare Workers AI (requires optional API key)
        logger.info("Falling back to Cloudflare Workers AI for image generation...")
        cf_path = await self.generate_cloudflare_background(keywords, vertical)
        if cf_path:
            return cf_path
        
        # 4. Fallback to procedural gradient
        logger.info("All AI generators failed. Generating procedural gradient fallback...")
        width, height = (720, 1280) if vertical else (1080, 1080)
        colors = self.theme.get("colors", {})
        img = self._generate_procedural_background(width, height, colors)
        fallback_path = self._temp_path(
            "procedural_fallback_v.jpg" if vertical else "procedural_fallback.jpg"
        )
        final_img = img.convert("RGB")
        final_img.save(fallback_path, "JPEG", quality=95)
        return fallback_path

    async def download_image(self, url: str) -> Optional[Path]:
        """Downloads a specific image URL to use as cover background"""
        img_path = self._temp_path("bg_downloaded.jpg")
        try:
            logger.info("Downloading a validated public news image for the cover")
            async with httpx.AsyncClient() as client:
                resp = await fetch_public_http(
                    client,
                    url,
                    timeout=15,
                    max_bytes=15 * 1024 * 1024,
                )
                if resp.status_code == 200:
                    with open(img_path, "wb") as f:
                        f.write(resp.content)

                    with Image.open(img_path) as downloaded_image:
                        width, height = downloaded_image.size
                        if (
                            width <= 0
                            or height <= 0
                            or width * height > MAX_DOWNLOADED_IMAGE_PIXELS
                        ):
                            raise ValueError("downloaded image dimensions are unsafe")
                        downloaded_image.verify()
                    logger.info("Successfully downloaded news cover background.")
                    return img_path
                else:
                    logger.warning(f"Failed to download news image. Status: {resp.status_code}")
        except Exception as e:
            img_path.unlink(missing_ok=True)
            logger.warning("Rejected or failed news background image (%s)", type(e).__name__)
        return None

    def _apply_glitch_effect(self, img: Image.Image) -> Image.Image:
        """Applies a cyber-glitch effect (color channel shift and scanlines)"""
        import random
        from PIL import ImageChops
        
        r, g, b = img.convert("RGB").split()
        
        # Shift channels horizontally
        shift_r = random.randint(-4, 4)
        shift_b = random.randint(-4, 4)
        
        r = ImageChops.offset(r, shift_r, 0)
        b = ImageChops.offset(b, shift_b, 0)
        
        glitched = Image.merge("RGB", (r, g, b))
        
        # Add subtle scanlines using an alpha-blended overlay to avoid harsh aliasing
        width, height = glitched.size
        scanline_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(scanline_overlay)
        
        for y in range(0, height, 4):
            draw_overlay.line([(0, y), (width, y)], fill=(0, 0, 0, 18), width=1)
            
        glitched_rgba = glitched.convert("RGBA")
        glitched_composite = Image.alpha_composite(glitched_rgba, scanline_overlay)
        return glitched_composite.convert("RGB")

    def _draw_tech_graphics(self, draw: ImageDraw.ImageDraw, width: int, height: int, colors: dict):
        """Draws minimal, clean decorative accents"""
        brand_accent = tuple(self._parse_color(colors.get("brand_accent"), [217, 4, 41, 255]))
        subtle_white = (255, 255, 255, 30)
        
        # Subtle top horizontal accent line
        line_w = int(width * 0.25)
        line_x = (width - line_w) // 2
        draw.line([(line_x, 60), (line_x + line_w, 60)], fill=subtle_white, width=1)
        # Small accent dot at center of line
        cx = width // 2
        draw.ellipse([cx - 2, 58, cx + 2, 62], fill=(brand_accent[0], brand_accent[1], brand_accent[2], 80))

    def _generate_procedural_background(self, width: int, height: int, colors: dict) -> Image.Image:
        """Generates a premium cyber tech style diagonal gradient background"""
        brand_accent = self._parse_color(colors.get("brand_accent"), [217, 4, 41, 255])
        bg_fallback = self._parse_color(colors.get("background_fallback"), [13, 15, 20, 255])
        
        # Calculate dynamic gaming gradient end-color (15% accent + 85% background fallback)
        grad_color1 = tuple(bg_fallback[:3] + [255])
        grad_color2 = (
            int(brand_accent[0] * 0.15 + bg_fallback[0] * 0.85),
            int(brand_accent[1] * 0.15 + bg_fallback[1] * 0.85),
            int(brand_accent[2] * 0.15 + bg_fallback[2] * 0.85),
            255
        )
        
        # Create a tiny 4x4 image and scale it up to create a smooth diagonal gradient
        grad_small = Image.new("RGBA", (4, 4))
        for x in range(4):
            for y in range(4):
                t = (x + y) / 6.0
                r = int(grad_color1[0] * (1 - t) + grad_color2[0] * t)
                g = int(grad_color1[1] * (1 - t) + grad_color2[1] * t)
                b = int(grad_color1[2] * (1 - t) + grad_color2[2] * t)
                grad_small.putpixel((x, y), (r, g, b, 255))
                
        img = grad_small.resize((width, height), Image.Resampling.BILINEAR)
        return img

    def create_cover(self, title: str, bg_path: Path = None, vertical: bool = False) -> Path:
        """Creates a text-overlay cover image with the channel's unified branding style.
        Uses robust font fallback and text stroke for guaranteed readability across all platforms."""
        width, height = (720, 1280) if vertical else (1080, 1080)
        output_name = "final_cover_v.jpg" if vertical else "final_cover.jpg"
        output_path = self._temp_path(output_name)
        
        try:
            colors = self.theme.get("colors", {})
            layout = self.theme.get("layout", {})
            brand_accent = tuple(self._parse_color(colors.get("brand_accent"), [217, 4, 41, 255]))
            text_primary = tuple(self._parse_color(colors.get("text_primary"), [255, 255, 255, 255]))
            brand_dark = self._parse_color(colors.get("brand_dark"), [13, 15, 20, 255])
            
            # 1. Load and crop background or create procedural fallback
            if bg_path and bg_path.exists():
                try:
                    bg_img = Image.open(bg_path).convert("RGBA")
                    img = self.smart_crop(bg_img, width, height)
                except Exception as e:
                    logger.error(f"Failed to load background image {bg_path}: {e}. Generating fallback.")
                    img = self._generate_procedural_background(width, height, colors)
            else:
                img = self._generate_procedural_background(width, height, colors)

            # Apply subtle glitch to background
            img = self._apply_glitch_effect(img).convert("RGBA")
            draw = ImageDraw.Draw(img)

            # 2. Strong dark vignette gradient from bottom for text readability
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            for y in range(height):
                # Stronger fade at bottom (80% opacity at bottom, 0% at top 30%)
                t = max(0, (y - int(height * 0.3)) / (height * 0.7))
                alpha = int(200 * (t ** 1.2))
                overlay_draw.line([(0, y), (width, y)], fill=(brand_dark[0], brand_dark[1], brand_dark[2], alpha), width=1)
            img = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(img)

            # 3. Minimalist HUD decorative elements
            # Subtle inner border
            offset = 24
            border_color = (255, 255, 255, 20)
            draw.rectangle([offset, offset, width - offset, height - offset], outline=border_color, width=1)
            
            # Corner L-brackets in accent color (aligned with border corners)
            bracket_len = 20
            bracket_offset = 24
            # Top-Left
            draw.line([(bracket_offset, bracket_offset), (bracket_offset + bracket_len, bracket_offset)], fill=brand_accent, width=2)
            draw.line([(bracket_offset, bracket_offset), (bracket_offset, bracket_offset + bracket_len)], fill=brand_accent, width=2)
            # Top-Right
            draw.line([(width - bracket_offset, bracket_offset), (width - bracket_offset - bracket_len, bracket_offset)], fill=brand_accent, width=2)
            draw.line([(width - bracket_offset, bracket_offset), (width - bracket_offset, bracket_offset + bracket_len)], fill=brand_accent, width=2)
            # Bottom-Left
            draw.line([(bracket_offset, height - bracket_offset), (bracket_offset + bracket_len, height - bracket_offset)], fill=brand_accent, width=2)
            draw.line([(bracket_offset, height - bracket_offset), (bracket_offset, height - bracket_offset - bracket_len)], fill=brand_accent, width=2)
            # Bottom-Right
            draw.line([(width - bracket_offset, height - bracket_offset), (width - bracket_offset - bracket_len, height - bracket_offset)], fill=brand_accent, width=2)
            draw.line([(width - bracket_offset, height - bracket_offset), (width - bracket_offset, height - bracket_offset - bracket_len)], fill=brand_accent, width=2)

            # 4. Top-center brand badge
            badge_text = self.theme.get("badge_text", "// NEUROSOFT GAMING //")
            badge_font = self._get_font(20)
            try:
                badge_w = badge_font.getlength(badge_text)
            except AttributeError:
                badge_w = len(badge_text) * 11
            draw.text(((width - badge_w) // 2, 40), badge_text, font=badge_font, fill=(255, 255, 255, 60))
            
            # Top accent line with dot (separated from text to prevent overlap)
            line_w = int(width * 0.25)
            line_x = (width - line_w) // 2
            draw.line([(line_x, 75), (line_x + line_w, 75)], fill=(255, 255, 255, 30), width=1)
            cx = width // 2
            draw.ellipse([cx - 2, 73, cx + 2, 77], fill=(brand_accent[0], brand_accent[1], brand_accent[2], 80))

            # 5. Headline Text Rendering with robust font — dynamic sizing, NO truncation
            base_font_size = layout.get("font_size_vertical", 48) if vertical else layout.get("font_size_square", 62)
            wrap_w = layout.get("wrap_width_vertical", 600) if vertical else layout.get("wrap_width_square", 900)
            
            clean_title = re.sub(r'<[^>]+>', '', title)
            clean_title = "".join(c for c in clean_title if ord(c) < 0x10000 and c not in '\ufeff\ufffe')
            clean_title = re.sub(r'\s+', ' ', clean_title).strip()
            
            # Dynamic font sizing: shrink font until text fits in max 5 lines and max 45% of height
            min_font_size = 28 if vertical else 36
            font_size = base_font_size
            while font_size >= min_font_size:
                font = self._get_font(font_size)
                lines = self._wrap_text(clean_title, font, wrap_w)
                total_h = len(lines) * (font_size + 12)
                if len(lines) <= 5 and total_h <= (height * 0.45):
                    break
                font_size -= 4
            
            wrapped_lines = lines
            line_spacing = font_size + 12
            total_text_height = len(wrapped_lines) * line_spacing
            pad_left = layout.get("padding_left_vertical", 60) if vertical else layout.get("padding_left_square", 90)
            
            # Card background for text (clean rectangle, ends above watermark)
            card_margin = 30
            card_x1 = pad_left - card_margin
            card_x2 = width - pad_left + card_margin
            card_y2 = height - 90  # Leave space for watermark at the bottom
            card_y1 = card_y2 - total_text_height - 40
            
            # Ensure card doesn't go too high
            if card_y1 < height * 0.5:
                card_y1 = height * 0.5
                card_y2 = card_y1 + total_text_height + 40
            
            card_fill = (brand_dark[0], brand_dark[1], brand_dark[2], 180)
            card_outline = (brand_accent[0], brand_accent[1], brand_accent[2], 100)
            draw.rounded_rectangle([card_x1, card_y1, card_x2, card_y2], fill=card_fill, outline=card_outline, width=2, radius=12)
            
            # Neon indicator bar on left side of card
            indicator_x = card_x1 + 10
            draw.line([(indicator_x, card_y1 + 15), (indicator_x, card_y2 - 15)], fill=(brand_accent[0], brand_accent[1], brand_accent[2], 80), width=6)
            draw.line([(indicator_x, card_y1 + 15), (indicator_x, card_y2 - 15)], fill=brand_accent, width=2)
            
            # Render text lines with stroke for readability
            y_start = card_y1 + 20
            
            for line in wrapped_lines:
                x_pos = pad_left
                # Draw black stroke (outline) for readability against any background
                stroke_color = (0, 0, 0, 200)
                for dx, dy in [(-2, -2), (-2, 0), (-2, 2), (0, -2), (0, 2), (2, -2), (2, 0), (2, 2)]:
                    draw.text((x_pos + dx, y_start + dy), line, font=font, fill=stroke_color)
                # Draw main text
                draw.text((x_pos, y_start), line, font=font, fill=text_primary)
                y_start += line_spacing
            
            # 6. Watermark at bottom
            wm_config = self.theme.get("watermark", {})
            wm_text_parts = wm_config.get("text_parts", [
                {"text": "/ игры ", "color_type": "primary"},
                {"text": "⚡", "color_type": "accent"},
                {"text": " патчи /", "color_type": "primary"}
            ])
            wm_font_size = wm_config.get("font_size", 24)
            wm_font = self._get_font(wm_font_size)
            full_wm = "".join([p["text"] for p in wm_text_parts])
            try:
                wm_w = wm_font.getlength(full_wm)
            except AttributeError:
                wm_w = len(full_wm) * 10
            wm_x = (width - wm_w) // 2
            wm_y = height - 50
            
            # Resolve watermark colors from theme if available
            wm_primary_color = tuple(self._parse_color(colors.get("watermark_text"), list(text_primary)))
            wm_accent_color = tuple(self._parse_color(colors.get("watermark_accent"), list(brand_accent)))
            
            for part in wm_text_parts:
                color_type = part.get("color_type", "primary")
                fill = wm_accent_color if color_type == "accent" else wm_primary_color
                draw.text((wm_x, wm_y), part["text"], font=wm_font, fill=fill)
                try:
                    part_w = wm_font.getlength(part["text"])
                except AttributeError:
                    part_w = len(part["text"]) * 10
                wm_x += part_w

            # Save as JPEG
            final_img = img.convert("RGB")
            final_img.save(output_path, "JPEG", quality=95)
            logger.info(f"Cover generated successfully at {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating cover: {e}", exc_info=True)
            # EMERGENCY FALLBACK: never return None, always generate a minimal cover
            try:
                logger.warning("Emergency fallback cover generation...")
                width, height = (720, 1280) if vertical else (1080, 1080)
                img = Image.new("RGB", (width, height), (13, 15, 20))
                draw = ImageDraw.Draw(img)
                font = self._get_font(42)
                safe_title = re.sub(r'<[^>]+>', '', title)[:100]
                safe_title = "".join(c for c in safe_title if ord(c) < 0x10000)
                lines = self._wrap_text(safe_title, font, width - 80)
                y = (height - len(lines) * 54) // 2
                for line in lines:
                    draw.text((40, y), line, font=font, fill=(255, 255, 255))
                    y += 54
                img.save(output_path, "JPEG", quality=90)
                return output_path
            except Exception as e2:
                logger.critical(f"Even emergency fallback failed: {e2}")
                return None

    def create_slide(self, caption: str, bg_path: Path = None, vertical: bool = True) -> Path:
        """Creates a clean, vertical Reels slide with large readable text and minimal design."""
        width, height = (720, 1280) if vertical else (1080, 1080)
        output_name = f"slide_{hash(caption) % 100000}.jpg"
        output_path = self._temp_path(output_name)

        try:
            colors = self.theme.get("colors", {})
            brand_accent = tuple(self._parse_color(colors.get("brand_accent"), [217, 4, 41, 255]))
            text_primary = tuple(self._parse_color(colors.get("text_primary"), [255, 255, 255, 255]))

            # 1. Background
            if bg_path and bg_path.exists():
                try:
                    bg_img = Image.open(bg_path).convert("RGBA")
                    w, h = bg_img.size
                    target_ratio = width / height
                    current_ratio = w / h
                    if current_ratio > target_ratio:
                        new_w = int(h * target_ratio)
                        left = (w - new_w) // 2
                        bg_img = bg_img.crop((left, 0, left + new_w, h))
                    else:
                        new_h = int(w / target_ratio)
                        top = (h - new_h) // 2
                        bg_img = bg_img.crop((0, top, w, top + new_h))
                    img = bg_img.resize((width, height), Image.Resampling.LANCZOS)
                except Exception as e:
                    logger.error(f"Failed to load background {bg_path}: {e}. Generating fallback.")
                    img = self._generate_procedural_background(width, height, colors)
            else:
                img = self._generate_procedural_background(width, height, colors)

            # Apply subtle glitch
            img = self._apply_glitch_effect(img).convert("RGBA")
            draw = ImageDraw.Draw(img)

            # 2. Dark gradient overlay for text readability (top to bottom)
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            for y in range(height):
                alpha = int(120 * (y / height))
                overlay_draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha), width=1)
            img = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(img)

            # 3. Minimalist border
            offset = 24
            border_color = (255, 255, 255, 20)
            draw.rectangle([offset, offset, width - offset, height - offset], outline=border_color, width=1)

            # 4. Badge at top
            badge_text = self.theme.get("badge_text", "// NEUROSOFT GAMING //")
            badge_font_size = 18
            badge_font = self._get_font(badge_font_size)
            try:
                badge_w = badge_font.getlength(badge_text)
            except AttributeError:
                badge_w = len(badge_text) * 9
            draw.text(((width - badge_w) // 2, 30), badge_text, font=badge_font, fill=(255, 255, 255, 60))

            # 5. Large Caption Text
            clean_caption = re.sub(r'<[^>]+>', '', caption)
            clean_caption = "".join(c for c in clean_caption if ord(c) < 0x10000 and c not in '\ufeff\ufffe')
            clean_caption = re.sub(r'\s+', ' ', clean_caption).strip().upper()

            # Dynamic font sizing to fit slide
            max_font_size = 72
            min_font_size = 36
            font_size = max_font_size
            wrap_w = width - 80
            lines = []
            while font_size >= min_font_size:
                font = self._get_font(font_size)
                lines = self._wrap_text(clean_caption, font, wrap_w)
                total_h = len(lines) * (font_size + 12)
                if total_h <= height * 0.45:
                    break
                font_size -= 4

            total_text_height = len(lines) * (font_size + 12)
            y_start = (height - total_text_height) // 2 + 40  # Slightly below center

            # Accent line above text
            line_w = min(width * 0.6, 400)
            line_x = (width - line_w) // 2
            draw.line([(line_x, y_start - 20), (line_x + line_w, y_start - 20)], fill=brand_accent, width=3)

            for line in lines:
                try:
                    line_w_px = font.getlength(line)
                except AttributeError:
                    line_w_px = len(line) * font_size * 0.6
                x_pos = (width - line_w_px) // 2
                # Draw shadow
                draw.text((x_pos + 2, y_start + 2), line, font=font, fill=(0, 0, 0, 180))
                draw.text((x_pos, y_start), line, font=font, fill=text_primary)
                y_start += font_size + 12

            # Accent line below text
            draw.line([(line_x, y_start + 10), (line_x + line_w, y_start + 10)], fill=brand_accent, width=3)

            # 6. Watermark at bottom
            wm_config = self.theme.get("watermark", {})
            wm_text_parts = wm_config.get("text_parts", [
                {"text": "/ игры ", "color_type": "primary"},
                {"text": "⚡", "color_type": "accent"},
                {"text": " патчи /", "color_type": "primary"}
            ])
            wm_font_size = wm_config.get("font_size", 20)
            wm_font = self._get_font(wm_font_size)
            full_wm = "".join([p["text"] for p in wm_text_parts])
            try:
                wm_w = wm_font.getlength(full_wm)
            except AttributeError:
                wm_w = len(full_wm) * 10
            wm_x = (width - wm_w) // 2
            wm_y = height - 60
            for part in wm_text_parts:
                color_type = part.get("color_type", "primary")
                if color_type == "accent":
                    fill = brand_accent
                else:
                    fill = text_primary
                draw.text((wm_x, wm_y), part["text"], font=wm_font, fill=fill)
                try:
                    part_w = wm_font.getlength(part["text"])
                except AttributeError:
                    part_w = len(part["text"]) * 10
                wm_x += part_w

            final_img = img.convert("RGB")
            final_img.save(output_path, "JPEG", quality=95)
            logger.info(f"Slide generated successfully at {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error creating slide: {e}", exc_info=True)
            return None

    def _get_font(self, size: int):
        """Returns a truetype font at the requested size, or a safe fallback."""
        if self.font_path and self.font_path.exists():
            try:
                return ImageFont.truetype(str(self.font_path), size)
            except Exception:
                pass
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    def smart_crop(self, img: Image.Image, target_w: int, target_h: int) -> Image.Image:
        """Intelligently crops the image by finding the region of highest visual detail/edges (saliency)."""
        w, h = img.size
        target_ratio = target_w / target_h
        current_ratio = w / h
        
        if abs(current_ratio - target_ratio) < 0.05:
            return img.resize((target_w, target_h), Image.Resampling.LANCZOS).convert("RGBA")
            
        # Convert to grayscale and apply edge detection to find the salient area
        from PIL import ImageFilter, ImageStat
        gray = img.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        
        if current_ratio > target_ratio:
            # Image is wider than target. We need to crop horizontally.
            crop_h = h
            crop_w = int(h * target_ratio)
            
            # Slide a window horizontally to find the max edge density
            best_x = 0
            max_edges = -1
            # Step by 10 pixels to be fast
            for x in range(0, w - crop_w + 1, 10):
                box = (x, 0, x + crop_w, crop_h)
                cropped_edges = edges.crop(box)
                edge_sum = sum(ImageStat.Stat(cropped_edges).sum)
                if edge_sum > max_edges:
                    max_edges = edge_sum
                    best_x = x
            crop_box = (best_x, 0, best_x + crop_w, h)
        else:
            # Image is taller than target. We need to crop vertically.
            crop_w = w
            crop_h = int(w / target_ratio)
            
            # Slide a window vertically
            best_y = 0
            max_edges = -1
            for y in range(0, h - crop_h + 1, 10):
                box = (0, y, crop_w, y + crop_h)
                cropped_edges = edges.crop(box)
                edge_sum = sum(ImageStat.Stat(cropped_edges).sum)
                if edge_sum > max_edges:
                    max_edges = edge_sum
                    best_y = y
            crop_box = (0, best_y, w, best_y + crop_h)
            
        return img.crop(crop_box).resize((target_w, target_h), Image.Resampling.LANCZOS).convert("RGBA")

    def _wrap_text(self, text: str, font, max_width: int) -> list:
        """Helper to wrap text nicely inside the cover width"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = " ".join(current_line + [word])
            try:
                w = font.getlength(test_line)
            except AttributeError:
                w = len(test_line) * 12
                
            if w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                
        if current_line:
            lines.append(" ".join(current_line))
            
        return lines
