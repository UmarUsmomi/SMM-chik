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

    def _format_markdown_to_html(self, text: str) -> str:
        """Converts double-asterisk markdown bold (**) to HTML bold tags (<b>) for Telegram
        and preserves valid allowed HTML tags while escaping any other HTML characters.
        Uses a robust token-splitting and whitelisting approach."""
        if not text:
            return ""
        import re
        import html
        
        # 1. Normalize by unescaping any pre-escaped HTML characters to get raw text
        raw_text = html.unescape(text)
        
        # 2. Convert raw double-asterisks to HTML bold tags
        raw_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', raw_text)
        
        # 3. Split the text into HTML tags and non-tag text segments
        parts = re.split(r'(<[^>]+>)', raw_text)
        
        allowed_tags = {
            '<b>', '</b>', '<strong>', '</strong>',
            '<i>', '</i>', '<em>', '</em>',
            '<code>', '</code>',
            '<pre>', '</pre>',
            '<blockquote>', '</blockquote>',
            '<blockquote expandable>',
            '<u>', '</u>', '<ins>', '</ins>',
            '<s>', '</s>', '<strike>', '</strike>', '<del>', '</del>',
            '<tg-spoiler>', '</tg-spoiler>'
        }
        
        result = []
        for i, part in enumerate(parts):
            if i % 2 == 1:
                # It's an HTML tag. Normalize it for comparison (strip and lower)
                tag_clean = part.strip().lower()
                
                # Check if it's whitelisted
                is_allowed = False
                if tag_clean in allowed_tags:
                    is_allowed = True
                elif tag_clean.startswith('<a ') or tag_clean.startswith('<code ') or tag_clean.startswith('<pre ') or tag_clean.startswith('<blockquote '):
                    # Keep complex allowed tags with attributes (e.g. href, language class, or expandable)
                    is_allowed = True
                    
                if is_allowed:
                    result.append(part)
                else:
                    # Escape unapproved HTML-like structures to render them safely as text
                    result.append(html.escape(part))
            else:
                # It's text between tags. Escape any HTML characters to protect Telegram HTML parser
                result.append(html.escape(part))
                
        return "".join(result)

    async def publish_text(self, title: str, text: str) -> bool:
        """Publishes a text post to the Telegram channel"""
        if not self.enabled:
            logger.info(f"[DRY-RUN] Publishing text post:\nTitle: {title}\nText:\n{text}")
            return True

        # Format with HTML tags
        formatted_message = f"<b>{self._escape_html(title)}</b>\n\n{self._format_markdown_to_html(text)}"
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.channel_id,
            "text": formatted_message,
            "parse_mode": "HTML",
            "link_preview_options": {
                "show_above_text": True
            }
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

        formatted_title = f"<b>{self._escape_html(title)}</b>"
        formatted_text = self._format_markdown_to_html(text)
        caption = f"{formatted_title}\n\n{formatted_text}"
        
        # Telegram photo caption limit is 1024 chars. Truncate text if too long.
        if len(caption) > 1024:
            logger.warning(f"Caption too long ({len(caption)} chars). Truncating to fit 1024 limit.")
            # Reserve space for title + ellipsis
            max_text_len = 1024 - len(formatted_title) - 10  # 10 for "\n\n" + "..."
            if max_text_len > 50:
                formatted_text = formatted_text[:max_text_len].rsplit('\n', 1)[0] + "..."
            else:
                formatted_text = formatted_text[:100] + "..."
            caption = f"{formatted_title}\n\n{formatted_text}"

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

    async def _generate_visual_prompt(self, title: str, text: str) -> str:
        """Generates a concise visual prompt (in English) for background image generation based on news content"""
        prompt = f"""
Analyze the following tech/gaming news post and generate a short, high-impact English visual search phrase/prompt (max 6 words, comma-separated) that describes a suitable background image for this news cover.
The prompt must describe a realistic or stylized tech/gaming concept, NOT abstract concepts, and must NOT contain any words like "photo", "image", "vector", "drawing", "illustration", "high-res", or the name of the news item if it's too specific.
Only return the comma-separated English keywords.

News Title: {title}
News Text: {text}

Example Outputs:
- quantum computer, laser, processor, laboratory
- artificial intelligence, neural network, glowing brain
- cyber soldier, sci-fi armor, neon city
- futuristic console, controller, gaming gear

Keywords:"""
        try:
            from smm_engine.utils.gemini_helper import generate_content_with_retry
            from smm_engine.config import GEMINI_MODEL
            
            logger.info("Generating visual prompt using Gemini...")
            res = await generate_content_with_retry(
                prompt,
                initial_model=GEMINI_MODEL,
                generation_config={"temperature": 0.3}
            )
            cleaned = res.strip().replace("\n", "").replace('"', '').replace("'", "")
            logger.info(f"Generated visual prompt: {cleaned}")
            return cleaned
        except Exception as e:
            logger.error(f"Failed to generate visual prompt: {e}")
            # Fallback to naive first 3 words of title
            import re
            words = re.findall(r'\w+', title)
            return ",".join(words[:3]) if words else "technology,gaming"

    async def publish_post_with_cover(self, title: str, text: str) -> bool:
        """Generates a branded cover image and publishes it as a photo post, falling back to text on failure"""
        try:
            from smm_engine.media.image_handler import ImageGenerator
            img_gen = ImageGenerator()
            
            # Generate visual prompt using Gemini instead of raw title words
            keywords = await self._generate_visual_prompt(title, text)
            
            logger.info(f"Generating cover for post with keywords: {keywords}")
            # Try AI generation first
            bg_path = await img_gen.generate_ai_background(keywords)
            if not bg_path:
                logger.info("AI background generation failed or skipped. Falling back to stock image...")
                bg_path = await img_gen.fetch_background(keywords)
            cover_path = img_gen.create_cover(title, bg_path)
            
            if cover_path and cover_path.exists():
                success = await self.publish_photo(title, text, str(cover_path))
                # Delete temporary cover path to save space
                try:
                    cover_path.unlink()
                    if bg_path and bg_path.exists():
                        bg_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temp cover files: {e}")
                
                if success:
                    return True
                
                logger.warning("Telegram photo publishing failed, falling back to text post...")
        except Exception as e:
            logger.error(f"Failed to publish post with cover, falling back to text: {e}")
            
        return await self.publish_text(title, text)
