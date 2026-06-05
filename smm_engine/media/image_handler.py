import os
import httpx
import logging
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
        """Creates a text-overlay cover image with glassmorphism-style dimming"""
        width, height = (720, 1280) if vertical else (1280, 720)
        output_name = "final_cover_v.jpg" if vertical else "final_cover.jpg"
        output_path = self.temp_dir / output_name
        
        try:
            # 1. Load background or create solid dark background if failed
            if bg_path and bg_path.exists():
                img = Image.open(bg_path).convert("RGBA")
            else:
                img = Image.new("RGBA", (width, height), (30, 30, 40, 255))

            # 2. Dim background to make text readable (dark semi-transparent overlay)
            overlay = Image.new("RGBA", img.size, (15, 15, 25, 150)) # deep blue-black overlay
            img = Image.alpha_composite(img, overlay)

            # 3. Add stylish colored glowing stripe on the left side
            draw = ImageDraw.Draw(img)
            draw.rectangle([0, 0, 15, height], fill=(235, 94, 40, 255)) # neon-orange accent

            # 4. Text preparation
            # Wrap text to fit screen width (leave margins)
            text_color = (255, 255, 255, 255)
            font_size = 42 if vertical else 54
            
            # Load Font
            if self.font_path and self.font_path.exists():
                font = ImageFont.truetype(str(self.font_path), font_size)
            else:
                font = ImageFont.load_default()

            wrap_w = 600 if vertical else 1100
            wrapped_lines = self._wrap_text(title, font, wrap_w)
            
            # Draw text
            y_start = (height - len(wrapped_lines) * (font_size + 15)) // 2 # vertically center
            
            for line in wrapped_lines:
                draw.text((60 if vertical else 80, y_start), line, font=font, fill=text_color)
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
            # Check length of the line
            # Pillow 10+ uses getlength or getbbox
            try:
                w = font.getlength(test_line)
            except AttributeError:
                # Fallback for old PIL versions or default font
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
