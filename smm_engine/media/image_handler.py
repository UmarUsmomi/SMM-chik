import os
import httpx
import logging
import yaml
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from pathlib import Path
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
        """Downloads a clean Roboto font if not present, otherwise uses default"""
        font_file = self.temp_dir / "Roboto-Bold.ttf"
        if not font_file.exists():
            try:
                logger.info("Downloading Roboto font for cover generation...")
                url = "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Bold.ttf"
                resp = httpx.get(url, timeout=15)
                if resp.status_code == 200:
                    with open(font_file, "wb") as f:
                        f.write(resp.content)
            except Exception as e:
                logger.error(f"Failed to download font: {e}")
                return None
        return font_file

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

    async def generate_ai_background(self, keywords: str = "technology,gaming", vertical: bool = False) -> Path:
        """Generates a relevant background image using Pollinations AI (free AI image generation)"""
        import urllib.parse
        img_path = self.temp_dir / ("bg_ai_v.jpg" if vertical else "bg_ai.jpg")
        width, height = (720, 1280) if vertical else (1080, 1080)
        
        # Optimize prompt for Pollinations AI
        clean_keywords = keywords.replace(",", " ")
        prompt = f"futuristic cyber tech style vector art representation of {clean_keywords}, high resolution, neon colors, synthwave gaming aesthetic"
        encoded_prompt = urllib.parse.quote(prompt)
        
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true&private=true"
        
        logger.info(f"Generating AI cover background using Pollinations: {prompt[:50]}...")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=25)
                if resp.status_code == 200:
                    with open(img_path, "wb") as f:
                        f.write(resp.content)
                    logger.info("Successfully generated AI background cover.")
                    return img_path
                else:
                    logger.warning(f"Failed to generate AI background. Status: {resp.status_code}")
        except Exception as e:
            logger.error(f"Error generating AI background image: {e}")
        return None

    async def fetch_background(self, keywords: str = "technology,computer", vertical: bool = False) -> Path:
        """Downloads a relevant background image from LoremFlickr"""
        img_path = self.temp_dir / ("bg_download_v.jpg" if vertical else "bg_download.jpg")
        width, height = (720, 1280) if vertical else (1280, 720)
        url = f"https://loremflickr.com/{width}/{height}/{keywords}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=15, follow_redirects=True)
                if resp.status_code == 200:
                    with open(img_path, "wb") as f:
                        f.write(resp.content)
                    return img_path
        except Exception as e:
            logger.error(f"Error fetching background image: {e}")
        return None

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
            
            # 1. Load and crop background or create solid dark background if failed
            if bg_path and bg_path.exists():
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
            else:
                bg_fallback = tuple(colors.get("background_fallback", [13, 15, 20, 255]))
                img = Image.new("RGBA", (width, height), bg_fallback)
 
            # 2. Dim background to make text readable (dark semi-transparent overlay)
            overlay_color = tuple(colors.get("overlay_dim", [13, 15, 20, 150]))
            overlay = Image.new("RGBA", img.size, overlay_color)
            img = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(img)
 
            # 3. Text preparation & wrapping
            text_color = tuple(colors.get("text_primary", [255, 255, 255, 255]))
            font_size = layout.get("font_size_vertical", 42) if vertical else layout.get("font_size_square", 56)
            
            # Load Font
            if self.font_path and self.font_path.exists():
                font = ImageFont.truetype(str(self.font_path), font_size)
            else:
                font = ImageFont.load_default()
 
            wrap_w = layout.get("wrap_width_vertical", 600) if vertical else layout.get("wrap_width_square", 900)
            wrapped_lines = self._wrap_text(title, font, wrap_w)
            
            # Position text to avoid overlapping the bottom branding
            if vertical:
                y_start = (height - len(wrapped_lines) * (font_size + 15)) // 2
            else:
                # Center text vertically within the top 800px
                y_start = (800 - len(wrapped_lines) * (font_size + 18)) // 2
            
            pad_left = layout.get("padding_left_vertical", 60) if vertical else layout.get("padding_left_square", 90)
            for line in wrapped_lines:
                draw.text((pad_left, y_start), line, font=font, fill=text_color)
                y_start += font_size + 18
 
            # 4. Draw Channel Branding Overlay (only for square covers)
            if not vertical:
                import random
                
                brand_dark = tuple(colors.get("brand_dark", [13, 15, 20, 255]))
                brand_accent = tuple(colors.get("brand_accent", [217, 4, 41, 255]))
                
                # Bottom-left black jagged block
                points_black = [(0, 800)]
                steps = 15
                for i in range(1, steps):
                    t = i / steps
                    x = int(500 * t)
                    y = int(800 + (1080 - 800) * t)
                    x += random.randint(-10, 10)
                    y += random.randint(-10, 10)
                    points_black.append((x, y))
                points_black.extend([(500, 1080), (0, 1080)])
                draw.polygon(points_black, fill=brand_dark)
                
                # Bottom-right red jagged block
                points_red = [(1080, 750)]
                for i in range(1, steps):
                    t = i / steps
                    x = int(1080 - (1080 - 700) * t)
                    y = int(750 + (1080 - 750) * t)
                    x += random.randint(-8, 8)
                    y += random.randint(-8, 8)
                    points_red.append((x, y))
                points_red.extend([(700, 1080), (1080, 1080)])
                draw.polygon(points_red, fill=brand_accent)
                
                # White paint splatter / halftone simulation along black block edge
                splatter_dark = tuple(colors.get("splatter_dark", [255, 255, 255, 180]))
                for _ in range(120):
                    t = random.random()
                    x = int(500 * t)
                    y = int(800 + (1080 - 800) * t)
                    cx = x + random.randint(-30, 30)
                    cy = y + random.randint(-30, 30)
                    r = random.randint(1, 4)
                    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=splatter_dark)
                    
                # Red paint splatter / halftone simulation along red block edge
                splatter_accent = tuple(colors.get("splatter_accent", [217, 4, 41, 180]))
                for _ in range(120):
                    t = random.random()
                    x = int(1080 - (1080 - 700) * t)
                    y = int(750 + (1080 - 750) * t)
                    cx = x + random.randint(-25, 25)
                    cy = y + random.randint(-25, 25)
                    r = random.randint(1, 3)
                    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=splatter_accent)
                    
                # Accent 3x3 dot grid on the black block
                start_x, start_y = 40, 1020
                for r in range(3):
                    for c in range(3):
                        cx = start_x + c * 15
                        cy = start_y + r * 15
                        draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=brand_accent)
                        
                # White crosses on the red block
                def draw_cross(cx, cy, size=10, width=2):
                    draw.line([(cx - size, cy), (cx + size, cy)], fill=(255, 255, 255, 255), width=width)
                    draw.line([(cx, cy - size), (cx, cy + size)], fill=(255, 255, 255, 255), width=width)
                draw_cross(980, 1020)
                draw_cross(1030, 980)
                
                # Watermark text
                font_size_wm = wm_config.get("font_size", 24)
                if self.font_path and self.font_path.exists():
                    font_wm = ImageFont.truetype(str(self.font_path), font_size_wm)
                else:
                    font_wm = ImageFont.load_default()
                    
                text_parts = wm_config.get("text_parts", [])
                
                # Calculate widths of all parts
                parts_measured = []
                total_w = 0
                for part in text_parts:
                    text_str = part.get("text", "")
                    color_type = part.get("color_type", "primary")
                    if color_type == "accent":
                        color = tuple(colors.get("watermark_accent", [217, 4, 41, 255]))
                    else:
                        color = tuple(colors.get("watermark_text", [255, 255, 255, 255]))
                        
                    try:
                        w = font_wm.getlength(text_str)
                    except AttributeError:
                        w = len(text_str) * 12
                        
                    total_w += w
                    parts_measured.append((text_str, color, w))
                    
                start_x = (1080 - total_w) // 2
                y_pos = 1025
                
                current_x = start_x
                for text_str, color, w in parts_measured:
                    draw.text((current_x, y_pos), text_str, font=font_wm, fill=color)
                    current_x += w
 
            # Save as JPEG
            final_img = img.convert("RGB")
            final_img.save(output_path, "JPEG", quality=90)
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
