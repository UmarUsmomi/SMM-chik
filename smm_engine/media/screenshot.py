import httpx
import logging
from typing import Optional
from pathlib import Path
from smm_engine.config import BASE_DIR

logger = logging.getLogger(__name__)

class ScreenshotGenerator:
    def __init__(self):
        self.temp_dir = BASE_DIR / "temp_media"
        self.temp_dir.mkdir(exist_ok=True)

    async def capture_url(self, url: str) -> Optional[Path]:
        """Captures a screenshot of the specified URL and saves it locally"""
        out_path = self.temp_dir / "page_screenshot.png"
        api_url = f"https://api.microlink.io/?url={url}&screenshot=true"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(api_url, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    screenshot_url = data.get("data", {}).get("screenshot", {}).get("url")
                    
                    if screenshot_url:
                        # Download actual image
                        img_resp = await client.get(screenshot_url, timeout=20)
                        if img_resp.status_code == 200:
                            with open(out_path, "wb") as f:
                                f.write(img_resp.content)
                            logger.info(f"Screenshot saved successfully at {out_path}")
                            return out_path
                else:
                    logger.error(f"Microlink API returned status code {resp.status_code}")
        except Exception as e:
            logger.error(f"Error capturing screenshot for {url}: {e}")
            
        return None
