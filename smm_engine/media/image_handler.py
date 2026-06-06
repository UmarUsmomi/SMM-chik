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

    async def generate_ai_background(self, keywords: str = "technology,gaming", vertical: bool = False) -> Path:
        """Generates a relevant background image using Pollinations AI (free AI image generation)"""
        import urllib.parse
        img_path = self.temp_dir / ("bg_ai_v.jpg" if vertical else "bg_ai.jpg")
        width, height = (720, 1280) if vertical else (1080, 1080)
        
        # Optimize prompt for Pollinations AI
        clean_keywords = keywords.replace(",", " ")
        prompt = f"futuristic cyber tech style vector art representation of {clean_keywords}, high resolution, neon colors, synthwave gaming aesthetic"
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Remove private=true to avoid payment/quota errors on Pollinations AI
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"
        
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
        
        # Clean and format keywords for LoremFlickr URL path (comma-separated, no spaces)
        clean_keywords = ",".join([k.strip().replace(" ", ",") for k in keywords.split(",") if k.strip()])
        url = f"https://loremflickr.com/{width}/{height}/{clean_keywords}"
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

            # 2. Apply vertical linear gradient overlay (makes background photo visible on top, dark at bottom)
            gradient_img = Image.new("RGBA", (1, 10))
            dark_color = colors.get("brand_dark", [13, 15, 20, 255])
            for y in range(10):
                t = y / 9.0
                alpha = int(40 + (242 - 40) * t)
                gradient_img.putpixel((0, y), (dark_color[0], dark_color[1], dark_color[2], alpha))
                
            overlay = gradient_img.resize(img.size, Image.Resampling.BILINEAR)
            img = Image.alpha_composite(img, overlay)
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

            # 4. Draw Watermarks / Logo Badges at the top
            font_size_wm = wm_config.get("font_size", 20)
            if self.font_path and self.font_path.exists():
                font_wm = ImageFont.truetype(str(self.font_path), font_size_wm)
            else:
                font_wm = ImageFont.load_default()
                
            # Draw Top-Left Brand Logo Badge (">_ CODE: ZERO")
            logo_prefix = ">_ "
            logo_text = "CODE: ZERO"
            
            try:
                prefix_w = font_wm.getlength(logo_prefix)
                text_w = font_wm.getlength(logo_text)
            except AttributeError:
                prefix_w = len(logo_prefix) * 10
                text_w = len(logo_text) * 10
                
            logo_total_w = prefix_w + text_w
            badge_padding_x = 16
            badge_padding_y = 8
            
            logo_x1 = 40
            logo_y1 = 40
            logo_x2 = logo_x1 + logo_total_w + 2 * badge_padding_x
            logo_y2 = logo_y1 + font_size_wm + 2 * badge_padding_y
            
            logo_bg = (dark_color[0], dark_color[1], dark_color[2], 200)
            draw.rounded_rectangle(
                [logo_x1, logo_y1, logo_x2, logo_y2],
                radius=6,
                fill=logo_bg,
                outline=brand_accent,
                width=1
            )
            
            draw.text((logo_x1 + badge_padding_x, logo_y1 + badge_padding_y - 2), logo_prefix, font=font_wm, fill=brand_accent)
            draw.text((logo_x1 + badge_padding_x + prefix_w, logo_y1 + badge_padding_y - 2), logo_text, font=font_wm, fill=(255, 255, 255, 255))
            
            # Draw Top-Right Theme Watermark Badge
            text_parts = wm_config.get("text_parts", [])
            parts_measured = []
            total_wm_w = 0
            for part in text_parts:
                text_str = part.get("text", "")
                color_type = part.get("color_type", "primary")
                if color_type == "accent":
                    color = tuple(colors.get("watermark_accent", [217, 4, 41, 255]))
                else:
                    color = tuple(colors.get("watermark_text", [255, 255, 255, 255]))
                
                part_font = font_wm
                if any(ord(c) > 127 and not (0x0400 <= ord(c) <= 0x04FF) for c in text_str):
                    for font_name in ["seguiemj.ttf", "arial.ttf", "msyh.ttc", "DejaVuSans.ttf", "NotoColorEmoji.ttf"]:
                        try:
                            part_font = ImageFont.truetype(font_name, font_size_wm)
                            break
                        except Exception:
                            continue
                            
                try:
                    w = part_font.getlength(text_str)
                except AttributeError:
                    w = len(text_str) * 10
                    
                total_wm_w += w
                parts_measured.append((text_str, color, w, part_font))
                
            wm_x2 = width - 40
            wm_x1 = wm_x2 - total_wm_w - 2 * badge_padding_x
            wm_y1 = 40
            wm_y2 = wm_y1 + font_size_wm + 2 * badge_padding_y
            
            draw.rounded_rectangle(
                [wm_x1, wm_y1, wm_x2, wm_y2],
                radius=6,
                fill=logo_bg,
                outline=(255, 255, 255, 40),
                width=1
            )
            
            current_x = wm_x1 + badge_padding_x
            for text_str, color, w, part_font in parts_measured:
                draw.text((current_x, wm_y1 + badge_padding_y - 2), text_str, font=part_font, fill=color)
                current_x += w

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
            clean_title = re.sub(r'^[^\w\s\dа-яА-ЯёЁ]+', '', clean_title).strip()
            
            if len(clean_title) > 60:
                clean_title = clean_title[:57].rsplit(' ', 1)[0] + "..."
            
            wrapped_lines = self._wrap_text(clean_title, font, wrap_w)
            
            # Position text at the bottom, leaving top 60% of background photo clean
            total_text_height = len(wrapped_lines) * (font_size + 15)
            y_start = height - total_text_height - 100
            
            pad_left = layout.get("padding_left_vertical", 60) if vertical else layout.get("padding_left_square", 90)
            shadow_color = (0, 0, 0, 180)
            
            for line in wrapped_lines:
                # Draw elegant drop shadow
                draw.text(
                    (pad_left + 2, y_start + 2),
                    line,
                    font=font,
                    fill=shadow_color
                )
                # Draw main text in white (no cheap stroke outline)
                draw.text(
                    (pad_left, y_start),
                    line,
                    font=font,
                    fill=text_color
                )
                y_start += font_size + 15

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
