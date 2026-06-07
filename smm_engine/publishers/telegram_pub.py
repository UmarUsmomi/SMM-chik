import httpx
import logging
import html
from typing import Optional, Any

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
        # Run unescape in a loop (up to 3 times) to handle double-escaped HTML entities
        raw_text = text
        for _ in range(3):
            unescaped = html.unescape(raw_text)
            if unescaped == raw_text:
                break
            raw_text = unescaped
        
        # Preprocess HTML lists and line breaks to be compatible with Telegram HTML parse mode
        raw_text = re.sub(r'<br\s*/?>', '\n', raw_text, flags=re.IGNORECASE)
        raw_text = re.sub(r'<p[^>]*>', '', raw_text, flags=re.IGNORECASE)
        raw_text = re.sub(r'</p>\s*', '\n\n', raw_text, flags=re.IGNORECASE)
        
        raw_text = re.sub(r'<(ul|ol)[^>]*>', '', raw_text, flags=re.IGNORECASE)
        raw_text = re.sub(r'</(ul|ol)>\s*', '', raw_text, flags=re.IGNORECASE)
        raw_text = re.sub(r'<li>\s*', '▫️ ', raw_text, flags=re.IGNORECASE)
        raw_text = re.sub(r'</li>\s*', '\n', raw_text, flags=re.IGNORECASE)
        
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

    def _truncate_html(self, html_text: str, max_raw_len: int) -> str:
        """Truncates HTML text to a maximum number of raw characters (including tags),
        while preserving and closing valid HTML tags properly.
        Ensures the final output length is strictly <= max_raw_len."""
        import re
        
        # If the whole text fits, just return it
        if len(html_text) <= max_raw_len:
            return html_text
            
        result = []
        current_len = 0
        open_tags = []
        pos = 0
        n = len(html_text)
        
        while pos < n:
            # Check if the entire remaining suffix fits
            remaining_suffix = html_text[pos:]
            if current_len + len(remaining_suffix) <= max_raw_len:
                result.append(remaining_suffix)
                current_len += len(remaining_suffix)
                pos = n
                break
                
            # Determine the next token
            char = html_text[pos]
            
            if char == '<':
                # It's a tag
                match = re.match(r'<[^>]+>', remaining_suffix)
                if match:
                    tag = match.group(0)
                    tag_len = len(tag)
                    
                    # Parse tag name and check if it is opening, closing, or self-closing
                    tag_clean = tag.strip().lower()
                    is_closing = tag_clean.startswith('</')
                    is_self_closing = tag_clean.endswith('/>') or tag_clean.startswith('<br') or tag_clean.startswith('<hr')
                    
                    # Extract tag name
                    if is_closing:
                        name_match = re.match(r'</([a-zA-Z0-9-]+)', tag_clean)
                        name = name_match.group(1) if name_match else ""
                    else:
                        name_match = re.match(r'<([a-zA-Z0-9-]+)', tag_clean)
                        name = name_match.group(1) if name_match else ""
                    
                    # Update stack copy to calculate required closing tags
                    temp_open_tags = list(open_tags)
                    if is_closing:
                        if temp_open_tags and temp_open_tags[-1] == name:
                            temp_open_tags.pop()
                    elif not is_self_closing and name:
                        temp_open_tags.append(name)
                        
                    closing_tags_len = sum(len(t) + 3 for t in temp_open_tags)
                    
                    # Check if this tag fits (including closing tags and ellipsis)
                    if current_len + tag_len + closing_tags_len + 3 <= max_raw_len:
                        # It fits! Commit the change
                        result.append(tag)
                        current_len += tag_len
                        open_tags = temp_open_tags
                        pos += tag_len
                    else:
                        # Doesn't fit, truncate here
                        break
                else:
                    # Malformed tag, treat '<' as normal char
                    closing_tags_len = sum(len(t) + 3 for t in open_tags)
                    if current_len + 1 + closing_tags_len + 3 <= max_raw_len:
                        result.append('<')
                        current_len += 1
                        pos += 1
                    else:
                        break
            elif char == '&':
                # It's an HTML entity
                match = re.match(r'&[a-zA-Z0-9#]+;', remaining_suffix)
                if match:
                    entity = match.group(0)
                    entity_len = len(entity)
                    closing_tags_len = sum(len(t) + 3 for t in open_tags)
                    
                    if current_len + entity_len + closing_tags_len + 3 <= max_raw_len:
                        result.append(entity)
                        current_len += entity_len
                        pos += entity_len
                    else:
                        break
                else:
                    # Treat as normal char
                    closing_tags_len = sum(len(t) + 3 for t in open_tags)
                    if current_len + 1 + closing_tags_len + 3 <= max_raw_len:
                        result.append('&')
                        current_len += 1
                        pos += 1
                    else:
                        break
            else:
                # Normal char
                closing_tags_len = sum(len(t) + 3 for t in open_tags)
                if current_len + 1 + closing_tags_len + 3 <= max_raw_len:
                    result.append(char)
                    current_len += 1
                    pos += 1
                else:
                    break
                    
        # If we broke before reaching the end, we need to append '...' and close open tags
        if pos < n:
            res_str = "".join(result)
            if res_str.endswith(' '):
                res_str = res_str[:-1]
            res_str += "..."
            for tag in reversed(open_tags):
                res_str += f"</{tag}>"
            return res_str
            
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
        # Leave a safety margin of 100 characters for title formatting, emojis, newlines and platform differences.
        max_caption_len = 1024 - 100
        max_raw_text_len = max_caption_len - len(formatted_title) - 2 # 2 for newlines
        if max_raw_text_len < 50:
            max_raw_text_len = 100  # Fallback minimum
            
        if len(caption) > max_caption_len:
            logger.warning(f"Caption too long (raw: {len(caption)} chars). Truncating to fit {max_caption_len} limit.")
            formatted_text = self._truncate_html(formatted_text, max_raw_text_len)
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

    async def _extract_og_image(self, url: str) -> Optional[str]:
        """Fetches the news article URL and extracts the og:image or twitter:image metadata"""
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            return None
        try:
            logger.info(f"Extracting og:image from news URL: {url}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=8, follow_redirects=True)
                if resp.status_code == 200:
                    html_content = resp.text
                    import re
                    match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
                    if not match:
                        match = re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:image["\']', html_content, re.IGNORECASE)
                    if not match:
                        match = re.search(r'<meta\s+(?:name|property)=["\']twitter:image["\']\s+content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
                    if match:
                        img_url = match.group(1)
                        if img_url.startswith("//"):
                            img_url = "https:" + img_url
                        elif img_url.startswith("/"):
                            from urllib.parse import urljoin
                            img_url = urljoin(url, img_url)
                        logger.info(f"Extracted image URL: {img_url}")
                        return img_url
        except Exception as e:
            logger.warning(f"Failed to parse og:image from page {url}: {e}")
        return None

    async def publish_post_with_cover(self, title: str, text: str, news_item_url: Optional[str] = None, raw_data: Optional[Any] = None) -> bool:
        """Generates a branded cover image (using the news article's actual image if available) and publishes it"""
        try:
            from smm_engine.media.image_handler import ImageGenerator
            img_gen = ImageGenerator()
            
            bg_path = None
            image_url = None
            
            # 1. Try to extract image URL from raw_data
            if raw_data:
                # If raw_data is passed as JSON string, parse it
                if isinstance(raw_data, str):
                    try:
                        import json
                        raw_data = json.loads(raw_data)
                    except Exception:
                        pass
                if isinstance(raw_data, dict):
                    image_url = raw_data.get("cover_image") or raw_data.get("social_image")
            
            # 2. If not found in raw_data, try to extract og:image from the article URL
            if not image_url and news_item_url:
                image_url = await self._extract_og_image(news_item_url)
                
            # 3. Try downloading the extracted news image
            if image_url:
                bg_path = await img_gen.download_image(image_url)
                
            # 4. Fallback to AI generation or stock download if no news image was found/downloaded
            if not bg_path:
                logger.info("No news image available or download failed. Falling back to AI generator...")
                keywords = await self._generate_visual_prompt(title, text)
                bg_path = await img_gen.generate_ai_background(keywords)
                if not bg_path:
                    logger.info("AI background generation failed. Falling back to stock image download...")
                    bg_path = await img_gen.fetch_background(keywords)
                    
            # 5. Render final cover using the background
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


