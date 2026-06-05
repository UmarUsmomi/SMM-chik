import httpx
import logging
from typing import Optional
from pathlib import Path
from smm_engine.config import BASE_DIR

logger = logging.getLogger(__name__)

class QRCodeGenerator:
    def __init__(self):
        self.temp_dir = BASE_DIR / "temp_media"
        self.temp_dir.mkdir(exist_ok=True)

    async def generate_qr(self, data: str, filename: str = "source_qr.png") -> Optional[Path]:
        """Generates a QR Code image using GoQR.me API and saves it locally"""
        out_path = self.temp_dir / filename
        # Encode data
        import urllib.parse
        encoded_data = urllib.parse.quote_plus(data)
        
        api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded_data}&format=png"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(api_url, timeout=15)
                if resp.status_code == 200:
                    with open(out_path, "wb") as f:
                        f.write(resp.content)
                    logger.info(f"QR Code generated successfully at {out_path}")
                    return out_path
                else:
                    logger.error(f"GoQR.me API returned status code {resp.status_code}")
        except Exception as e:
            logger.error(f"Error generating QR Code: {e}")
            
        return None
