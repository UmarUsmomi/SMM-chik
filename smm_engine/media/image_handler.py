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

    def _setup_font(self) -> Path:
        """Returns the path to the bundled Montserrat-Bold font"""
        font_file = Path(__file__).resolve().parent.parent.parent / "fonts" / "Montserrat-Bold.ttf"
        if font_file.exists():
            logger.info(f"Using bundled Montserrat-Bold font: {font_file}")
            return font_file
            
        # Fallback to download if it does not exist for some reason
        temp_font = self.temp_dir / "Montserrat-Bold.ttf"
        if not temp_font.exists():
            try:
                logger.info("Downloading Montserrat-Bold font...")
                url = "https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Bold.ttf"
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

    # Curated high-quality tech/gaming backgrounds to use when other image APIs fail
    CURATED_BACKGROUNDS = [
        "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?w=1280&fit=crop&q=80",  # Gaming setup neon
        "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=1280&fit=crop&q=80",  # Gaming controller
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1280&fit=crop&q=80",  # Microchip tech
        "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1280&fit=crop&q=80",  # Abstract cyber tech
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=1280&fit=crop&q=80",  # Matrix coding
        "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=1280&fit=crop&q=80",  # Cybersecurity tech
        "https://images.unsplash.com/photo-1563089145-599997674d42?w=1280&fit=crop&q=80",  # Abstract neon synthwave
        "https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=1280&fit=crop&q=80",  # Developer code
        "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?w=1280&fit=crop&q=80",  # Gaming room neon
        "https://images.unsplash.com/photo-1478760329108-5c3ed9d495a0?w=1280&fit=crop&q=80",  # Abstract dark tech
    ]

    async def generate_hf_background(self, keywords: str, vertical: bool = False) -> Path:
        """Generates background using Hugging Face Serverless Inference API"""
        from smm_engine.config import HUGGINGFACE_API_KEY
        if not HUGGINGFACE_API_KEY:
            return None
            
        img_path = self.temp_dir / ("bg_hf_v.jpg" if vertical else "bg_hf.jpg")
        width, height = (720, 1280) if vertical else (1080, 1080)
        clean_keywords = keywords.replace(",", " ")
        prompt = f"cyberpunk synthwave hacker matrix code rain background {clean_keywords}, masterpiece, highly detailed, neon lights"
        
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

    async def generate_horde_background(self, keywords: str, vertical: bool = False) -> Path:
        """Generates background using AI Horde"""
        img_path = self.temp_dir / ("bg_horde_v.jpg" if vertical else "bg_horde.jpg")
        width, height = (512, 768) if vertical else (512, 512)
        
        clean_keywords = keywords.replace(",", " ")
        prompt = f"cyberpunk matrix code rain glowing background {clean_keywords}, high resolution, hacker synthwave aesthetic"
        
        url = "https://aihorde.net/api/v2/generate/async"
        headers = {
            "apikey": "0000000000",
            "Client-Agent": "SMM-Bot:1.0:production"
        }
        payload = {
            "prompt": prompt,
            "params": {"n": 1, "width": width, "height": height, "steps": 15, "cfg_scale": 7.0}
        }
        
        logger.info(f"Generating AI cover using AI Horde: {prompt[:60]}...")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=15)
                if resp.status_code != 202:
                    return None
                
                job_id = resp.json().get("id")
                if not job_id: return None
                    
                import asyncio
                for i in range(15):
                    await asyncio.sleep(3)
                    check_resp = await client.get(f"https://aihorde.net/api/v2/generate/check/{job_id}", timeout=10)
                    if check_resp.status_code == 200 and check_resp.json().get("done"):
                        status_resp = await client.get(f"https://aihorde.net/api/v2/generate/status/{job_id}", timeout=10)
                        if status_resp.status_code == 200:
                            gens = status_resp.json().get("generations", [])
                            if gens:
                                img_resp = await client.get(gens[0].get("img"), timeout=15)
                                if img_resp.status_code == 200:
                                    with open(img_path, "wb") as f:
                                        f.write(img_resp.content)
                                    return img_path
                    elif check_resp.status_code != 200:
                        break
        except Exception as e:
            logger.error(f"Error calling AI Horde: {e}")
        return None

    async def generate_ai_background(self, keywords: str = "technology,gaming", vertical: bool = False) -> Path:
        """Routes between Hugging Face and AI Horde based on availability"""
        hf_path = await self.generate_hf_background(keywords, vertical)
        if hf_path:
            return hf_path
            
        logger.info("Falling back to AI Horde for image generation...")
        return await self.generate_horde_background(keywords, vertical)
 
    async def fetch_background(self, keywords: str = "technology,computer", vertical: bool = False) -> Path:
        """Downloads a relevant background image from LoremFlickr or falls back to Unsplash curated list"""
        img_path = self.temp_dir / ("bg_download_v.jpg" if vertical else "bg_download.jpg")
        width, height = (720, 1280) if vertical else (1280, 720)
        
        # 1. Try to download from LoremFlickr using cache buster and topic tags
        import random
        random_lock = random.randint(1, 100000)
        
        # Use first 2 keywords for a more specific tag search on LoremFlickr
        kw_list = [k.strip().replace(" ", "") for k in keywords.split(",") if k.strip()]
        search_tags = kw_list[:2] if kw_list else ["technology", "gaming"]
        clean_keywords = ",".join(search_tags)
        
        # We query with /all (AND) first, fallback to /any if unsuccessful
        for search_mode in ["all", "any"]:
            url = f"https://loremflickr.com/{width}/{height}/{clean_keywords}/{search_mode}?lock={random_lock}"
            try:
                logger.info(f"Attempting to download background from LoremFlickr ({search_mode}): {url}")
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=12, follow_redirects=True)
                    if resp.status_code == 200:
                        # Check if it returned a placeholder/cat image or an actual image
                        # If size is small or if we got redirected to some cat picture, we still accept it as last resort,
                        # but if it fails we fall back to curated.
                        with open(img_path, "wb") as f:
                            f.write(resp.content)
                        logger.info("Successfully downloaded background from LoremFlickr.")
                        return img_path
            except Exception as e:
                logger.warning(f"LoremFlickr download failed with mode {search_mode}: {e}")
                
        # 2. Final Fallback: Select a random high-quality curated background
        fallback_url = random.choice(self.CURATED_BACKGROUNDS)
        logger.info(f"Falling back to high-quality curated tech background: {fallback_url}")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(fallback_url, timeout=15, follow_redirects=True)
                if resp.status_code == 200:
                    with open(img_path, "wb") as f:
                        f.write(resp.content)
                    logger.info("Successfully downloaded curated fallback background.")
                    return img_path
        except Exception as e:
            logger.error(f"Failed to download curated background fallback: {e}")
            
        return None

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
        
        # Add subtle scanlines
        draw = ImageDraw.Draw(glitched)
        width, height = glitched.size
        for y in range(0, height, 4):
            draw.line([(0, y), (width, y)], fill=(0, 0, 0), width=1)
            
        return glitched

    def _draw_tech_graphics(self, draw: ImageDraw.ImageDraw, width: int, height: int, colors: dict):
        """Draws subtle, high-tech graphical HUD elements and circuit node paths to fill the background"""
        import math
        brand_accent = tuple(colors.get("brand_accent", [217, 4, 41, 255]))
        
        # Opacities
        accent_alpha = (brand_accent[0], brand_accent[1], brand_accent[2], 30) # ~12% opacity
        white_alpha = (255, 255, 255, 20) # ~8% opacity
        dot_accent = (brand_accent[0], brand_accent[1], brand_accent[2], 80) # higher opacity for accent nodes
        dot_white = (255, 255, 255, 60) # higher opacity for white node borders
        
        # 1. Concentric HUD scanning reticle (placed in upper-middle area)
        cx, cy = width // 2, int(height * 0.38)
        
        # Draw central reticle circle layers
        draw.ellipse([cx - 130, cy - 130, cx + 130, cy + 130], outline=accent_alpha, width=1)
        draw.ellipse([cx - 135, cy - 135, cx + 135, cy + 135], outline=white_alpha, width=1)
        draw.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], outline=accent_alpha, width=1)
        
        # Tick marks on the outer ring (8 directions)
        for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
            rad = math.radians(angle)
            x1 = cx + int(135 * math.cos(rad))
            y1 = cy + int(135 * math.sin(rad))
            x2 = cx + int(145 * math.cos(rad))
            y2 = cy + int(145 * math.sin(rad))
            draw.line([(x1, y1), (x2, y2)], fill=accent_alpha, width=1)
            
        # Draw small crosshair lines in the very center
        draw.line([(cx - 25, cy), (cx - 8, cy)], fill=white_alpha, width=1)
        draw.line([(cx + 8, cy), (cx + 25, cy)], fill=white_alpha, width=1)
        draw.line([(cx, cy - 25), (cx, cy - 8)], fill=white_alpha, width=1)
        draw.line([(cx, cy + 8), (cx, cy + 25)], fill=white_alpha, width=1)
        
        # 2. Draw procedural tech circuits / graphical data-node lines
        # Define coordinates for nice geometric sci-fi circuit lines
        circuits = [
            # Circuit 1 (top-left)
            [(60, 160), (180, 160), (220, 200)],
            # Circuit 2 (top-right)
            [(width - 60, 160), (width - 180, 160), (width - 220, 200)],
            # Circuit 3 (middle-left)
            [(60, cy - 30), (140, cy - 30), (180, cy + 10)],
            # Circuit 4 (middle-right)
            [(width - 60, cy - 30), (width - 140, cy - 30), (width - 180, cy + 10)]
        ]
        
        for path in circuits:
            # Draw circuit path lines
            for i in range(len(path) - 1):
                draw.line([path[i], path[i+1]], fill=white_alpha, width=1)
            # Draw small circuit nodes/junction points
            for idx, node in enumerate(path):
                # Put a larger dot at the start or end of the circuit path
                dot_size = 3 if idx == 0 or idx == len(path)-1 else 2
                draw.ellipse(
                    [node[0] - dot_size, node[1] - dot_size, node[0] + dot_size, node[1] + dot_size],
                    fill=dot_accent,
                    outline=dot_white,
                    width=1
                )

        # 3. Draw tech diagnostic tick scales along the top/bottom inner borders
        offset = 24
        tick_y_top = offset + 1
        tick_y_bottom = height - offset - 4
        
        for x in range(offset + 60, width - offset - 60, 40):
            # Draw tiny ticks
            is_major = (x - offset) % 160 == 0
            tick_h = 6 if is_major else 3
            draw.line([(x, tick_y_top), (x, tick_y_top + tick_h)], fill=white_alpha, width=1)
            draw.line([(x, tick_y_bottom), (x, tick_y_bottom - tick_h)], fill=white_alpha, width=1)

        # 4. Small HUD corner labels (using Montserrat-Bold or system font)
        hud_font_size = 12
        if self.font_path and self.font_path.exists():
            hud_font = ImageFont.truetype(str(self.font_path), hud_font_size)
        else:
            hud_font = ImageFont.load_default()
            
        draw.text((offset + 12, offset + 8), "SYS_INIT //", font=hud_font, fill=white_alpha)
        draw.text((width - offset - 90, offset + 8), "ONLINE [85%]", font=hud_font, fill=white_alpha)


    def _generate_procedural_background(self, width: int, height: int, colors: dict) -> Image.Image:
        """Generates a premium cyber tech style diagonal gradient background with a subtle grid overlay"""
        brand_accent = colors.get("brand_accent", [217, 4, 41, 255])
        bg_fallback = colors.get("background_fallback", [13, 15, 20, 255])
        
        # Calculate dynamic gradient end-color (15% accent + 85% background fallback)
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
        draw = ImageDraw.Draw(img)
        
        # Draw tech grid overlay (low opacity accent color)
        grid_color = (brand_accent[0], brand_accent[1], brand_accent[2], 12)
        spacing = 60
        for x in range(0, width, spacing):
            draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
        for y in range(0, height, spacing):
            draw.line([(0, y), (width, y)], fill=grid_color, width=1)
            
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
            dark_color = colors.get("brand_dark", [13, 15, 20, 255])
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
            brand_accent = tuple(colors.get("brand_accent", [217, 4, 41, 255]))
            
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
            badge_text = "// NEUROSOFT GAMING //"
            badge_font_size = 20
            if self.font_path and self.font_path.exists():
                badge_font = ImageFont.truetype(str(self.font_path), badge_font_size)
            else:
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
            text_color = tuple(colors.get("text_primary", [255, 255, 255, 255]))
            font_size = layout.get("font_size_vertical", 42) if vertical else layout.get("font_size_square", 56)
            
            if self.font_path and self.font_path.exists():
                font = ImageFont.truetype(str(self.font_path), font_size)
            else:
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
            y_start = height - total_text_height - 80
            
            pad_left = layout.get("padding_left_vertical", 60) if vertical else layout.get("padding_left_square", 90)
            shadow_color = (0, 0, 0, 200)
            glow_color = (brand_accent[0], brand_accent[1], brand_accent[2], 80) # Semi-transparent accent glow
            
            for line in wrapped_lines:
                # Simple clean text with a soft shadow for readability (no messy glow)
                draw.text(
                    (pad_left + 3, y_start + 3),
                    line,
                    font=font,
                    fill=shadow_color
                )
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
