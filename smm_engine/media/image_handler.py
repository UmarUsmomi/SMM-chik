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

    async def generate_horde_background(self, keywords: str, vertical: bool = False) -> Path:
        """Generates background using AI Horde"""
        img_path = self.temp_dir / ("bg_horde_v.jpg" if vertical else "bg_horde.jpg")
        width, height = (512, 768) if vertical else (512, 512)
        
        clean_keywords = keywords.replace(",", " ")
        prompt = (
            f"dark high-contrast techno-gaming background of {clean_keywords}, cyberpunk hacker style, "
            "glowing neon cyan and hot red circuit lines, digital grid overlay, futuristic HUD reticle "
            "in upper half, clean dark bottom region, deep shadows, cinematic lighting, highly detailed "
            "### text, words, letters, logo, signature, watermark, bright background, white background, "
            "daylight, out of focus, crowded bottom, blurry"
        )
        
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

        # 1. Concentric HUD scanning reticle (placed in upper-middle area)
        cx, cy = width // 2, int(height * 0.38)
        
        # Draw central reticle circle layers
        draw.ellipse([cx - 130, cy - 130, cx + 130, cy + 130], outline=(brand_accent[0], brand_accent[1], brand_accent[2], 30), width=1)
        draw.ellipse([cx - 135, cy - 135, cx + 135, cy + 135], outline=(255, 255, 255, 20), width=1)
        draw.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], outline=(brand_accent[0], brand_accent[1], brand_accent[2], 30), width=1)
        
        # Tick marks on the outer ring (8 directions)
        for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
            rad = math.radians(angle)
            x1 = cx + int(135 * math.cos(rad))
            y1 = cy + int(135 * math.sin(rad))
            x2 = cx + int(145 * math.cos(rad))
            y2 = cy + int(145 * math.sin(rad))
            draw.line([(x1, y1), (x2, y2)], fill=(brand_accent[0], brand_accent[1], brand_accent[2], 30), width=1)
            
        # Draw small crosshair lines in the very center
        draw.line([(cx - 25, cy), (cx - 8, cy)], fill=(255, 255, 255, 20), width=1)
        draw.line([(cx + 8, cy), (cx + 25, cy)], fill=(255, 255, 255, 20), width=1)
        draw.line([(cx, cy - 25), (cx, cy - 8)], fill=(255, 255, 255, 20), width=1)
        draw.line([(cx, cy + 8), (cx, cy + 25)], fill=(255, 255, 255, 20), width=1)
        
        # 2. Premium Coordinate Grid Overlay (drawn on any background)
        offset = 24
        grid_spacing = 80
        grid_min_x = offset + 40
        grid_max_x = width - offset - 40
        grid_min_y = offset + 40
        grid_max_y = height - offset - 40
        
        # Faint line opacities
        grid_white = (255, 255, 255, 8)
        grid_accent = (brand_accent[0], brand_accent[1], brand_accent[2], 12)
        
        # Draw grid lines and coordinate labels
        for x in range(grid_min_x, grid_max_x, grid_spacing):
            # Vertical lines
            draw.line([(x, grid_min_y), (x, grid_max_y)], fill=grid_white, width=1)
            # Label at top axis
            label_x = f"X_{x:03d}"
            draw.text((x - 12, offset + 26), label_x, font=coord_font, fill=(255, 255, 255, 30))
            
        for y in range(grid_min_y, grid_max_y, grid_spacing):
            # Horizontal lines
            draw.line([(grid_min_x, y), (grid_max_x, y)], fill=grid_white, width=1)
            # Label at left axis
            label_y = f"Y_{y:03d}"
            draw.text((offset + 26, y - 5), label_y, font=coord_font, fill=(255, 255, 255, 30))
            
        # Draw small intersection crosses (plus signs "+") outside central reticle
        cross_size = 3
        for x in range(grid_min_x, grid_max_x, grid_spacing):
            for y in range(grid_min_y, grid_max_y, grid_spacing):
                dist_to_center = math.sqrt((x - cx)**2 + (y - cy)**2)
                # Keep the center and the bottom text area (headline) clean
                if dist_to_center > 160 and y < height - 260:
                    draw.line([(x - cross_size, y), (x + cross_size, y)], fill=grid_accent, width=1)
                    draw.line([(x, y - cross_size), (x, y + cross_size)], fill=grid_accent, width=1)

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
            badge_text = "// NEUROSOFT GAMING //"
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

            # 6. Render Branded Watermark in Bottom-Right Corner (R1)
            if wm_config:
                wm_font_size = wm_config.get("font_size", 24)
                if self.font_path and self.font_path.exists():
                    wm_font = ImageFont.truetype(str(self.font_path), wm_font_size)
                else:
                    try:
                        wm_font = ImageFont.load_default(size=wm_font_size)
                    except TypeError:
                        wm_font = ImageFont.load_default()

                text_parts = wm_config.get("text_parts", [])
                
                # Calculate widths of text segments
                part_widths = []
                for part in text_parts:
                    txt = part.get("text", "")
                    try:
                        w = wm_font.getlength(txt)
                    except AttributeError:
                        w = len(txt) * (wm_font_size * 0.5)
                    part_widths.append(w)
                
                total_wm_width = sum(part_widths)
                try:
                    ascent, descent = wm_font.getmetrics()
                    wm_height = ascent + descent
                except (AttributeError, TypeError):
                    wm_height = wm_font_size

                # Align with bottom-right boundaries (inner border offset = 24)
                x_end = width - offset - 16
                y_end = height - offset - 16
                
                wm_x_start = x_end - total_wm_width
                wm_y_start = y_end - wm_height
                
                # Retrieve theme-configured colors
                watermark_text_color = tuple(self._parse_color(colors.get("watermark_text", colors.get("text_primary")), [255, 255, 255, 255]))
                watermark_accent_color = tuple(self._parse_color(colors.get("watermark_accent", colors.get("brand_accent")), [217, 4, 41, 255]))
                brand_dark = self._parse_color(colors.get("brand_dark"), [13, 15, 20, 255])
                brand_accent = self._parse_color(colors.get("brand_accent"), [217, 4, 41, 255])
                
                # Draw semi-transparent backing box for perfect readability
                pad_x = 12
                pad_y = 6
                back_x1 = wm_x_start - pad_x
                back_y1 = wm_y_start - pad_y
                back_x2 = x_end + pad_x
                back_y2 = y_end + pad_y
                
                backing_fill = tuple(brand_dark[:3] + [180])  # ~70% opacity
                backing_outline = tuple(brand_accent[:3] + [80])   # low opacity accent border
                
                try:
                    draw.rounded_rectangle(
                        [back_x1, back_y1, back_x2, back_y2],
                        radius=6,
                        fill=backing_fill,
                        outline=backing_outline,
                        width=1
                    )
                except AttributeError:
                    draw.rectangle(
                        [back_x1, back_y1, back_x2, back_y2],
                        fill=backing_fill,
                        outline=backing_outline,
                        width=1
                    )
                
                # Render the text segments
                current_x = wm_x_start
                for idx, part in enumerate(text_parts):
                    txt = part.get("text", "")
                    color_type = part.get("color_type", "primary")
                    part_color = watermark_text_color if color_type == "primary" else watermark_accent_color
                    
                    draw.text(
                        (current_x, wm_y_start),
                        txt,
                        font=wm_font,
                        fill=tuple(part_color),
                        stroke_width=1,
                        stroke_fill=tuple(brand_dark[:3] + [255])
                    )
                    current_x += part_widths[idx]
            
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
