import os
import httpx
import logging
import yaml
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from pathlib import Path
from typing import Optional, Any
from smm_engine.config import BASE_DIR

logger = logging.getLogger(__name__)

class ImageGenerator:
    def __init__(self):
        self.temp_dir = BASE_DIR / "temp_media"
        self.temp_dir.mkdir(exist_ok=True)
        # Choose a basic font path or download one
        self.font_path = self._setup_font()
        # Load active theme configuration
        self.theme = self._load_theme()

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
        """Returns the path to the bundled RussoOne-Regular font"""
        font_file = Path(__file__).resolve().parent.parent.parent / "fonts" / "RussoOne-Regular.ttf"
        if font_file.exists():
            logger.info(f"Using bundled RussoOne-Regular font: {font_file}")
            return font_file
            
        # Fallback to download if it does not exist for some reason
        temp_font = self.temp_dir / "RussoOne-Regular.ttf"
        if not temp_font.exists():
            try:
                logger.info("Downloading RussoOne-Regular font...")
                url = "https://github.com/google/fonts/raw/main/ofl/russoone/RussoOne-Regular.ttf"
                resp = httpx.get(url, timeout=15)
                if resp.status_code == 200:
                    with open(temp_font, "wb") as f:
                        f.write(resp.content)
                    return temp_font
            except Exception as e:
                logger.error(f"Failed to download font: {e}")
        return temp_font if temp_font.exists() else None

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


    async def generate_hf_background(self, keywords: str, vertical: bool = False) -> Path:
        """Generates background using Hugging Face Serverless Inference API"""
        from smm_engine.config import HUGGINGFACE_API_KEY
        if not HUGGINGFACE_API_KEY:
            return None
            
        img_path = self.temp_dir / ("bg_hf_v.jpg" if vertical else "bg_hf.jpg")
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
        
        logger.info(f"Generating AI cover using Hugging Face: {prompt[:60]}...")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(api_url, headers=headers, json=payload, timeout=45)
                if resp.status_code == 200:
                    with open(img_path, "wb") as f:
                        f.write(resp.content)
                    return img_path
                else:
                    logger.warning(f"Hugging Face API failed: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Error calling Hugging Face API: {e}")
        return None

    async def generate_pollinations_background(self, keywords: str, vertical: bool = False) -> Path:
        """Generates background using Pollinations.ai — fully free, no API key needed.
        Uses a simple GET request with the prompt encoded in the URL."""
        import urllib.parse
        
        img_path = self.temp_dir / ("bg_poll_v.jpg" if vertical else "bg_poll.jpg")
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
            f"?width={width}&height={height}&nologo=true&seed={hash(keywords) % 100000}"
        )
        
        logger.info(f"Generating AI cover using Pollinations.ai: {prompt[:60]}...")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=30, follow_redirects=True)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    with open(img_path, "wb") as f:
                        f.write(resp.content)
                    logger.info("Successfully generated background via Pollinations.ai")
                    return img_path
                else:
                    logger.warning(f"Pollinations.ai failed: status={resp.status_code}, size={len(resp.content)}")
        except Exception as e:
            logger.error(f"Error calling Pollinations.ai: {e}")
        return None

    async def generate_cloudflare_background(self, keywords: str, vertical: bool = False) -> Path:
        """Generates background using Cloudflare Workers AI REST API.
        Requires CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN env variables.
        Uses @cf/black-forest-labs/flux-1-schnell model with 10,000 free neurons/day."""
        from smm_engine.config import CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN
        if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
            return None
        
        img_path = self.temp_dir / ("bg_cf_v.jpg" if vertical else "bg_cf.jpg")
        
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
                resp = await client.post(api_url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    with open(img_path, "wb") as f:
                        f.write(resp.content)
                    logger.info("Successfully generated background via Cloudflare Workers AI")
                    return img_path
                else:
                    logger.warning(f"Cloudflare Workers AI failed: status={resp.status_code}")
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
        fallback_path = self.temp_dir / ("procedural_fallback_v.jpg" if vertical else "procedural_fallback.jpg")
        final_img = img.convert("RGB")
        final_img.save(fallback_path, "JPEG", quality=95)
        return fallback_path

    async def download_image(self, url: str) -> Optional[Path]:
        """Downloads a specific image URL to use as cover background"""
        img_path = self.temp_dir / "bg_downloaded.jpg"
        try:
            logger.info(f"Downloading news image to use as background: {url}")
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=15, follow_redirects=True)
                if resp.status_code == 200:
                    with open(img_path, "wb") as f:
                        f.write(resp.content)
                    logger.info("Successfully downloaded news cover background.")
                    return img_path
                else:
                    logger.warning(f"Failed to download news image. Status: {resp.status_code}")
        except Exception as e:
            logger.error(f"Error downloading news background image: {e}")
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
        """Draws subtle, high-tech graphical HUD elements, coordinate grids, and circuit node paths to fill the background"""
        import math
        brand_accent = tuple(self._parse_color(colors.get("brand_accent"), [217, 4, 41, 255]))
        
        # Setup small font for coordinate grids and technical labels
        coord_font_size = 9
        if self.font_path and self.font_path.exists():
            coord_font = ImageFont.truetype(str(self.font_path), coord_font_size)
        else:
            try:
                coord_font = ImageFont.load_default(size=coord_font_size)
            except TypeError:
                coord_font = ImageFont.load_default()

        # Helper to draw a high-tech glowing junction node
        def draw_glow_node(cx: int, cy: int, is_accent: bool = True):
            color = brand_accent if is_accent else (255, 255, 255, 255)
            # Outer glow (large, faint)
            glow_rad = 6
            draw.ellipse([cx - glow_rad, cy - glow_rad, cx + glow_rad, cy + glow_rad], fill=(color[0], color[1], color[2], 25))
            # Mid ring (medium, medium opacity)
            mid_rad = 3
            draw.ellipse([cx - mid_rad, cy - mid_rad, cx + mid_rad, cy + mid_rad], outline=(color[0], color[1], color[2], 100), width=1)
            # Inner core (small, solid)
            core_rad = 1.5
            draw.ellipse([cx - core_rad, cy - core_rad, cx + core_rad, cy + core_rad], fill=(color[0], color[1], color[2], 220))

        # Helper to draw component codes
        def draw_label(text: str, x: int, y: int, align: str = "left"):
            try:
                text_w = coord_font.getlength(text)
            except AttributeError:
                text_w = len(text) * 6
            draw_x = x - text_w if align == "right" else x
            draw.text((draw_x, y - 5), text, font=coord_font, fill=(255, 255, 255, 45))

        offset = 24

        # 3. Dynamic & Aspect-Ratio Aware Sci-Fi Circuit Paths
        circuit_y1 = int(height * 0.15)
        circuit_y2 = int(height * 0.45)
        
        # Parallel data bus lines (spaced 6px apart) for top-left
        bus_offset = 6
        circuits_list = [
            # Top-Left Parallel Bus Track A
            {"path": [(48, circuit_y1), (160, circuit_y1), (200, circuit_y1 + 40)], "labels": {0: "BUS_L0", 2: "R12"}, "glows": [2]},
            # Top-Left Parallel Bus Track B
            {"path": [(48, circuit_y1 + bus_offset), (160 - 2, circuit_y1 + bus_offset), (200 - 2, circuit_y1 + 40 + bus_offset)], "labels": {}, "glows": [2]},
            
            # Top-Right Chip Interface
            {"path": [(width - 48, circuit_y1), (width - 160, circuit_y1), (width - 200, circuit_y1 + 40)], "labels": {0: "IC_CLK", 2: "C23"}, "glows": [2]},
            
            # Mid-Left Telemetry
            {"path": [(48, circuit_y2), (120, circuit_y2), (160, circuit_y2 + 40)], "labels": {0: "TX_0", 2: "GND"}, "glows": [0, 2]},
            # Mid-Right Telemetry
            {"path": [(width - 48, circuit_y2), (width - 120, circuit_y2), (width - 160, circuit_y2 + 40)], "labels": {0: "RX_1", 2: "VCC"}, "glows": [0, 2]}
        ]
        
        for c in circuits_list:
            path = c["path"]
            glows = c.get("glows", [])
            labels = c.get("labels", {})
            
            # Draw circuit path segments
            for i in range(len(path) - 1):
                draw.line([path[i], path[i+1]], fill=(255, 255, 255, 20), width=1)
                
            # Draw nodes and component labels
            for idx, node in enumerate(path):
                if idx in glows:
                    draw_glow_node(node[0], node[1], is_accent=True)
                else:
                    dot_size = 2.5 if idx == 0 or idx == len(path)-1 else 1.5
                    draw.ellipse(
                        [node[0] - dot_size, node[1] - dot_size, node[0] + dot_size, node[1] + dot_size],
                        fill=(brand_accent[0], brand_accent[1], brand_accent[2], 80),
                        outline=(255, 255, 255, 60),
                        width=1
                    )
                if idx in labels:
                    align = "right" if node[0] > width // 2 else "left"
                    offset_x = -8 if align == "right" else 8
                    draw_label(labels[idx], node[0] + offset_x, node[1], align=align)

        # 4. Draw tech diagnostic tick scales along the top/bottom inner borders
        tick_y_top = offset + 1
        tick_y_bottom = height - offset - 4
        
        for x in range(offset + 60, width - offset - 60, 40):
            is_major = (x - offset) % 160 == 0
            tick_h = 6 if is_major else 3
            draw.line([(x, tick_y_top), (x, tick_y_top + tick_h)], fill=(255, 255, 255, 20), width=1)
            draw.line([(x, tick_y_bottom), (x, tick_y_bottom - tick_h)], fill=(255, 255, 255, 20), width=1)

        # 5. Small HUD corner labels (using Montserrat-Bold or system font)
        hud_font_size = 12
        if self.font_path and self.font_path.exists():
            hud_font = ImageFont.truetype(str(self.font_path), hud_font_size)
        else:
            try:
                hud_font = ImageFont.load_default(size=hud_font_size)
            except TypeError:
                hud_font = ImageFont.load_default()
            
        draw.text((offset + 12, offset + 8), "SYS_INIT //", font=hud_font, fill=(255, 255, 255, 20))
        draw.text((width - offset - 90, offset + 8), "ONLINE [85%]", font=hud_font, fill=(255, 255, 255, 20))

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
        """Creates a text-overlay cover image with the channel's unified branding style"""
        width, height = (720, 1280) if vertical else (1080, 1080)
        output_name = "final_cover_v.jpg" if vertical else "final_cover.jpg"
        output_path = self.temp_dir / output_name
        
        try:
            # Extract theme parameters
            colors = self.theme.get("colors", {})
            layout = self.theme.get("layout", {})
            wm_config = self.theme.get("watermark", {})
            
            # 1. Load and crop background or create procedural gradient background if failed
            if bg_path and bg_path.exists():
                try:
                    bg_img = Image.open(bg_path).convert("RGBA")
                    w, h = bg_img.size
                    if vertical:
                        # Center crop to 9:16 aspect ratio
                        target_ratio = 720 / 1280
                        current_ratio = w / h
                        if current_ratio > target_ratio:
                            new_w = int(h * target_ratio)
                            left = (w - new_w) // 2
                            bg_img = bg_img.crop((left, 0, left + new_w, h))
                        else:
                            new_h = int(w / target_ratio)
                            top = (h - new_h) // 2
                            bg_img = bg_img.crop((0, top, w, top + new_h))
                        img = bg_img.resize((720, 1280), Image.Resampling.LANCZOS)
                    else:
                        # Center crop to 1:1 square
                        min_dim = min(w, h)
                        left = (w - min_dim) // 2
                        top = (h - min_dim) // 2
                        bg_img = bg_img.crop((left, top, left + min_dim, top + min_dim))
                        img = bg_img.resize((1080, 1080), Image.Resampling.LANCZOS)
                except Exception as e:
                    logger.error(f"Failed to load background image {bg_path}: {e}. Generating fallback.")
                    img = self._generate_procedural_background(width, height, colors)
            else:
                img = self._generate_procedural_background(width, height, colors)

            # Apply glitch to background BEFORE drawing text
            img = self._apply_glitch_effect(img).convert("RGBA")

            # 2. Apply dark gradient overlay to make text readable
            gradient_img = Image.new("RGBA", (1, int(height * 0.7)))
            dark_color = self._parse_color(colors.get("brand_dark"), [13, 15, 20, 255])
            for y in range(gradient_img.height):
                t = y / float(gradient_img.height)
                # Exponential gradient for smoother fade
                alpha = int(255 * (t ** 1.5))
                gradient_img.putpixel((0, y), (dark_color[0], dark_color[1], dark_color[2], alpha))
                
            overlay = gradient_img.resize((width, height), Image.Resampling.BILINEAR)
            # Paste gradient at the bottom
            temp_overlay = Image.new("RGBA", img.size)
            temp_overlay.paste(overlay, (0, int(height * 0.3)))
            img = Image.alpha_composite(img, temp_overlay)
            draw = ImageDraw.Draw(img)
 
            # 3. Draw minimalist HUD decorative elements
            brand_accent = tuple(self._parse_color(colors.get("brand_accent"), [217, 4, 41, 255]))
            
            # Subtle inner border (thin line, 1px, low opacity)
            offset = 24
            border_color = (255, 255, 255, 20)
            draw.rectangle(
                [offset, offset, width - offset, height - offset],
                outline=border_color,
                width=1
            )
            
            # Corner L-brackets (crop marks) in accent color
            bracket_len = 20
            bracket_offset = 20
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

            # 4. Tech graphics and minimalist channel badge
            self._draw_tech_graphics(draw, width, height, colors)
            
            # Subtle top-center brand badge (fully graphic-themed, no raw game/patch text)
            badge_text = self.theme.get("badge_text", "// NEUROSOFT GAMING //")
            badge_font_size = 20
            if self.font_path and self.font_path.exists():
                badge_font = ImageFont.truetype(str(self.font_path), badge_font_size)
            else:
                try:
                    badge_font = ImageFont.load_default(size=badge_font_size)
                except TypeError:
                    badge_font = ImageFont.load_default()
            
            try:
                badge_w = badge_font.getlength(badge_text)
            except AttributeError:
                badge_w = len(badge_text) * 11
                
            draw.text(
                ((width - badge_w) // 2, 40),
                badge_text,
                font=badge_font,
                fill=(255, 255, 255, 60) # semi-transparent white
            )

            # 5. Headline Text Rendering
            text_color = tuple(self._parse_color(colors.get("text_primary"), [255, 255, 255, 255]))
            font_size = layout.get("font_size_vertical", 42) if vertical else layout.get("font_size_square", 56)
            
            if self.font_path and self.font_path.exists():
                font = ImageFont.truetype(str(self.font_path), font_size)
            else:
                try:
                    font = ImageFont.load_default(size=font_size)
                except TypeError:
                    font = ImageFont.load_default()
 
            wrap_w = layout.get("wrap_width_vertical", 600) if vertical else layout.get("wrap_width_square", 900)
            
            import re
            clean_title = re.sub(r'<[^>]+>', '', title)
            clean_title = "".join(c for c in clean_title if ord(c) < 0x2000)
            clean_title = re.sub(r'\s+', ' ', clean_title).strip()
            
            # Remove anything that looks like body text accidentally appended to title
            # If there's a strong separator or newline that was flattened, or if it's too long
            if len(clean_title) > 65:
                # Try to cut at punctuation
                match = re.search(r'([.!?])\s+[А-ЯA-Z]', clean_title)
                if match and match.start() < 65:
                    clean_title = clean_title[:match.start() + 1]
                else:
                    clean_title = clean_title[:62].rsplit(' ', 1)[0] + "..."
            
            wrapped_lines = self._wrap_text(clean_title, font, wrap_w)
            
            # Position text at the bottom
            total_text_height = len(wrapped_lines) * (font_size + 10)
            y_start_initial = height - total_text_height - 80
            y_start_final = height - 80
            
            pad_left = layout.get("padding_left_vertical", 60) if vertical else layout.get("padding_left_square", 90)
            brand_dark = self._parse_color(colors.get("brand_dark"), [13, 15, 20, 255])
            
            # Card bounds
            card_x1 = 24 if vertical else (pad_left - 30)
            card_x2 = width - pad_left + 30
            card_y1 = y_start_initial - 20
            card_y2 = y_start_final + 20
            
            # Fill the card with a semi-transparent dark color
            card_fill = (brand_dark[0], brand_dark[1], brand_dark[2], 200)
            # Draw a thin border of accent color
            card_outline = (brand_accent[0], brand_accent[1], brand_accent[2], 120)
            
            # Draw polygon for Cyberpunk 2077 cut look (cut top-left by 15px)
            polygon_pts = [
                (card_x1 + 15, card_y1),
                (card_x2, card_y1),
                (card_x2, card_y2),
                (card_x1, card_y2),
                (card_x1, card_y1 + 15)
            ]
            draw.polygon(polygon_pts, fill=card_fill, outline=card_outline, width=1)
            
            # Vertical neon indicator bar of the accent color to the left of the text block
            indicator_x = card_x1 + 8
            indicator_y1 = card_y1 + 20
            indicator_y2 = card_y2 - 10
            # Glow line: width 6
            draw.line([(indicator_x, indicator_y1), (indicator_x, indicator_y2)], fill=(brand_accent[0], brand_accent[1], brand_accent[2], 60), width=6)
            # Core line: width 2
            draw.line([(indicator_x, indicator_y1), (indicator_x, indicator_y2)], fill=(brand_accent[0], brand_accent[1], brand_accent[2], 255), width=2)
            
            # Render the headline text lines left-aligned on the card using the Russo One font
            y_start = y_start_initial
            for line in wrapped_lines:
                draw.text(
                    (pad_left, y_start),
                    line,
                    font=font,
                    fill=text_color
                )
                y_start += font_size + 10
            
            # Save as JPEG
            final_img = img.convert("RGB")
            final_img.save(output_path, "JPEG", quality=95)
            logger.info(f"Cover generated successfully at {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating cover: {e}", exc_info=True)
            return None

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
