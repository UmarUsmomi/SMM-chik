import os
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
import google.generativeai as genai

from smm_engine.config import BASE_DIR, GEMINI_API_KEY
from smm_engine.media.image_handler import ImageGenerator

logger = logging.getLogger(__name__)

class VideoGenerator:
    def __init__(self):
        self.image_gen = ImageGenerator()
        self.temp_dir = BASE_DIR / "temp_media"
        self.temp_dir.mkdir(exist_ok=True)
        self.enabled = bool(GEMINI_API_KEY)

    async def generate_reel(self, news_title: str, news_text: str) -> Optional[Path]:
        """Generates a vertical Reels slideshow MP4 video using Gemini storyboard and ffmpeg"""
        if not self.enabled:
            logger.info("[DRY-RUN] Generating video storyboard for: " + news_title)
            return None

        # 1. Ask Gemini to create a 3-slide storyboard
        storyboard = await self._generate_storyboard(news_title, news_text)
        if not storyboard or len(storyboard) < 2:
            logger.error("Failed to generate a valid storyboard from Gemini")
            return None

        logger.info(f"Storyboard generated with {len(storyboard)} slides. Compiling slide frames...")
        
        slide_paths = []
        for i, slide in enumerate(storyboard):
            try:
                caption = slide.get("caption", "")
                bg_keywords = slide.get("background_keywords", "technology")
                
                # Fetch background
                bg_path = await self.image_gen.fetch_background(bg_keywords, vertical=True)
                
                # Create vertical slide frame
                slide_img = self.image_gen.create_cover(caption, bg_path=bg_path, vertical=True)
                if slide_img and slide_img.exists():
                    # Move to unique path for compilation
                    dest_path = self.temp_dir / f"frame_{i}.jpg"
                    if dest_path.exists():
                        dest_path.unlink()
                    slide_img.rename(dest_path)
                    slide_paths.append(dest_path)
            except Exception as e:
                logger.error(f"Error compiling slide {i}: {e}")

        if len(slide_paths) < 2:
            logger.error("Not enough slide frames compiled successfully")
            return None

        # 2. Build and run ffmpeg command
        output_video_path = self.temp_dir / "output_reel.mp4"
        if output_video_path.exists():
            try:
                output_video_path.unlink()
            except Exception as e:
                logger.error(f"Failed to remove existing video: {e}")
                return None

        success = self._run_ffmpeg(slide_paths, output_video_path)
        if success and output_video_path.exists():
            logger.info(f"Reel video compiled successfully at {output_video_path}")
            return output_video_path
            
        return None

    async def _generate_storyboard(self, title: str, text: str) -> Optional[List[Dict[str, str]]]:
        """Asks Gemini to design a 3-slide visual storyboard and caption script"""
        prompt = f"""
You are a video editor and scriptwriter. Your task is to design a 3-slide storyboard for a vertical Reel/Short video based on this tech news:

News Title: "{title}"
News Body: "{text}"

For each slide, you need to provide:
1. "caption": A very short, punchy Russian caption text to overlay on the screen (maximum 5-7 words, large font).
2. "background_keywords": 2-3 English search keywords for a relevant background image (e.g. "code,computer", "gaming,neon", "neural,artificial").

The slideshow flow:
- Slide 0: Hook / Intro (What is the shocking/cool news?)
- Slide 1: Detail / Body (How does it work or why is it cool?)
- Slide 2: Outro / CTA (Join the channel / what is your opinion?)

Return ONLY a JSON array of 3 objects in this format:
[
  {{
    "caption": "КАЙФОВЫЙ ХУК-ЗАГОЛОВОК",
    "background_keywords": "cyberpunk,coding"
  }},
  {{
    "caption": "СУТЬ И ФАКТЫ О НОВОСТИ",
    "background_keywords": "server,matrix"
  }},
  {{
    "caption": "ПОДПИШИСЬ НА КАНАЛ!",
    "background_keywords": "gaming,neon"
  }}
]
"""
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.8
                }
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Error generating video storyboard: {e}")
            return None

    def _run_ffmpeg(self, slide_paths: List[Path], output_path: Path) -> bool:
        """Invokes local ffmpeg to assemble slides with fading transitions"""
        # Command syntax for ffmpeg fading slideshow
        # We loop each image for 4 seconds, using fade transitions of 0.5s
        
        inputs = []
        for path in slide_paths:
            inputs.extend(["-loop", "1", "-t", "4", "-i", str(path)])
            
        # Filter complex for transitions:
        # slide 0 (0:v) fade out at 3.5s
        # slide 1 (1:v) fade in at 0s, out at 3.5s
        # slide 2 (2:v) fade in at 0s
        n = len(slide_paths)
        filter_parts = []
        
        # Build fade filters
        for i in range(n):
            in_fade = f"fade=t=in:st=0:d=0.5," if i > 0 else ""
            out_fade = f"fade=t=out:st=3.5:d=0.5" if i < n-1 else ""
            
            # Combine
            if in_fade or out_fade:
                # Remove trailing comma if out_fade is empty
                f_str = f"{in_fade}{out_fade}".rstrip(",")
                filter_parts.append(f"[{i}:v]{f_str}[v{i}];")
            else:
                filter_parts.append(f"[{i}:v]copy[v{i}];")
                
        # Concat part
        concat_inputs = "".join([f"[v{i}]" for i in range(n)])
        filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=0[v]")
        
        filter_complex = "".join(filter_parts)
        
        cmd = [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", "25",
            str(output_path)
        ]
        
        try:
            logger.info("Executing ffmpeg: " + " ".join(cmd))
            # Run command silently
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                return True
            else:
                logger.error(f"ffmpeg failed with return code {res.returncode}. Stderr: {res.stderr}")
                return False
        except FileNotFoundError:
            logger.error("ffmpeg executable not found in system PATH. Cannot compile video.")
            return False
        except Exception as e:
            logger.error(f"Exception during ffmpeg process: {e}")
            return False
