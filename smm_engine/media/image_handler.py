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
        """Creates a text-overlay cover image with the channel's unified branding style"""
        width, height = (720, 1280) if vertical else (1080, 1080)
        output_name = "final_cover_v.jpg" if vertical else "final_cover.jpg"
        output_path = self.temp_dir / output_name
        
        try:
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
                img = Image.new("RGBA", (width, height), (13, 15, 20, 255))
 
            # 2. Dim background to make text readable (dark semi-transparent overlay)
            overlay = Image.new("RGBA", img.size, (13, 15, 20, 150))
            img = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(img)
 
            # 3. Text preparation & wrapping
            text_color = (255, 255, 255, 255)
            font_size = 42 if vertical else 56
            
            # Load Font
            if self.font_path and self.font_path.exists():
                font = ImageFont.truetype(str(self.font_path), font_size)
            else:
                font = ImageFont.load_default()
 
            wrap_w = 600 if vertical else 900
            wrapped_lines = self._wrap_text(title, font, wrap_w)
            
            # Position text to avoid overlapping the bottom branding
            if vertical:
                y_start = (height - len(wrapped_lines) * (font_size + 15)) // 2
            else:
                # Center text vertically within the top 800px
                y_start = (800 - len(wrapped_lines) * (font_size + 18)) // 2
            
            for line in wrapped_lines:
                draw.text((60 if vertical else 90, y_start), line, font=font, fill=text_color)
                y_start += font_size + 18
 
            # 4. Draw Channel Branding Overlay (only for square covers)
            if not vertical:
                import random
                
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
                draw.polygon(points_black, fill=(13, 15, 20, 255))
                
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
                draw.polygon(points_red, fill=(217, 4, 41, 255))
                
                # White paint splatter / halftone simulation along black block edge
                for _ in range(120):
                    t = random.random()
                    x = int(500 * t)
                    y = int(800 + (1080 - 800) * t)
                    cx = x + random.randint(-30, 30)
                    cy = y + random.randint(-30, 30)
                    r = random.randint(1, 4)
                    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 180))
                    
                # Red paint splatter / halftone simulation along red block edge
                for _ in range(120):
                    t = random.random()
                    x = int(1080 - (1080 - 700) * t)
                    y = int(750 + (1080 - 750) * t)
                    cx = x + random.randint(-25, 25)
                    cy = y + random.randint(-25, 25)
                    r = random.randint(1, 3)
                    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(217, 4, 41, 180))
                    
                # Red 3x3 dot grid on the black block
                dot_radius = 5
                spacing = 15
                start_x, start_y = 40, 1020
                for r in range(3):
                    for c in range(3):
                        cx = start_x + c * spacing
                        cy = start_y + r * spacing
                        draw.ellipse([cx - dot_radius, cy - dot_radius, cx + dot_radius, cy + dot_radius], fill=(217, 4, 41, 255))
                        
                # White crosses on the red block
                def draw_cross(cx, cy, size=10, width=2):
                    draw.line([(cx - size, cy), (cx + size, cy)], fill=(255, 255, 255, 255), width=width)
                    draw.line([(cx, cy - size), (cx, cy + size)], fill=(255, 255, 255, 255), width=width)
                draw_cross(980, 1020)
                draw_cross(1030, 980)
                
                # Watermark text "/ игры ⚡ патчи /" in the bottom center
                font_size_wm = 24
                if self.font_path and self.font_path.exists():
                    font_wm = ImageFont.truetype(str(self.font_path), font_size_wm)
                else:
                    font_wm = ImageFont.load_default()
                    
                part1 = "/ игры "
                part2 = "⚡"
                part3 = " патчи /"
                
                try:
                    w1 = font_wm.getlength(part1)
                    w2 = font_wm.getlength(part2)
                    w3 = font_wm.getlength(part3)
                except AttributeError:
                    w1, w2, w3 = len(part1)*12, len(part2)*12, len(part3)*12
                    
                total_w = w1 + w2 + w3
                start_x = (1080 - total_w) // 2
                y_pos = 1025
                
                draw.text((start_x, y_pos), part1, font=font_wm, fill=(255, 255, 255, 255))
                draw.text((start_x + w1, y_pos), part2, font=font_wm, fill=(217, 4, 41, 255)) # red lightning symbol
                draw.text((start_x + w1 + w2, y_pos), part3, font=font_wm, fill=(255, 255, 255, 255))
 
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
