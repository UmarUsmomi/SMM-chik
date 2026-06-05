import httpx
import logging
import html
from typing import Optional

from smm_engine.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

logger = logging.getLogger(__name__)

class TelegramPublisher:
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.channel_id = TELEGRAM_CHANNEL_ID
        self.enabled = bool(self.bot_token and self.channel_id)
        if not self.enabled:
            logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID is missing. Publisher will run in dry-run mode.")

    def _escape_html(self, text: str) -> str:
        """Escapes text for Telegram HTML parse mode"""
        if not text:
            return ""
        # Simply escape HTML tags
        return html.escape(text)

    async def publish_text(self, title: str, text: str) -> bool:
        """Publishes a text post to the Telegram channel"""
        if not self.enabled:
            logger.info(f"[DRY-RUN] Publishing text post:\nTitle: {title}\nText:\n{text}")
            return True

        # Format with HTML tags
        formatted_message = f"<b>{self._escape_html(title)}</b>\n\n{text}"
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.channel_id,
            "text": formatted_message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=15)
                if resp.status_code == 200:
                    logger.info("Successfully published text post to Telegram")
                    return True
                else:
                    logger.error(f"Failed to publish to Telegram. Status: {resp.status_code}, Body: {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"Error publishing to Telegram: {e}")
            return False

    async def publish_photo(self, title: str, text: str, photo_url_or_path: str) -> bool:
        """Publishes a post with a photo/cover to the Telegram channel"""
        if not self.enabled:
            logger.info(f"[DRY-RUN] Publishing photo post:\nTitle: {title}\nPhoto: {photo_url_or_path}\nText:\n{text}")
            return True

        caption = f"<b>{self._escape_html(title)}</b>\n\n{text}"
        url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        
        try:
            async with httpx.AsyncClient() as client:
                # Check if it's a URL or local file path
                if photo_url_or_path.startswith("http://") or photo_url_or_path.startswith("https://"):
                    payload = {
                        "chat_id": self.channel_id,
                        "photo": photo_url_or_path,
                        "caption": caption,
                        "parse_mode": "HTML"
                    }
                    resp = await client.post(url, json=payload, timeout=20)
                else:
                    # Local file path
                    with open(photo_url_or_path, "rb") as f:
                        files = {"photo": f}
                        data = {
                            "chat_id": self.channel_id,
                            "caption": caption,
                            "parse_mode": "HTML"
                        }
                        resp = await client.post(url, data=data, files=files, timeout=30)
                        
                if resp.status_code == 200:
                    logger.info("Successfully published photo post to Telegram")
                    return True
                else:
                    logger.error(f"Failed to publish photo to Telegram. Status: {resp.status_code}, Body: {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"Error publishing photo to Telegram: {e}")
            return False
