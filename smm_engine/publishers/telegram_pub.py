import httpx
import logging
import html
import os
from typing import Optional, Any

from smm_engine.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from smm_engine.utils.network import fetch_public_http

logger = logging.getLogger(__name__)

class TelegramPublisher:
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.channel_id = TELEGRAM_CHANNEL_ID
        self.enabled = bool(self.bot_token and self.channel_id)
        environment = (os.getenv("ENVIRONMENT") or "").strip().lower()
        self.production = environment in {"production", "prod"} or bool(
            os.getenv("RENDER_EXTERNAL_URL")
        )
        if not self.enabled:
            if self.production:
                logger.error("Telegram publisher credentials are missing in production")
            else:
                logger.warning("Telegram publisher credentials are missing; using local dry-run mode")

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
        
        # Convert Markdown blockquotes (lines starting with "> ") to HTML blockquote tags
        # Collect consecutive "> " lines into a single <blockquote expandable> block
        lines = raw_text.split('\n')
        converted_lines = []
        in_quote = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('> '):
                if not in_quote:
                    converted_lines.append('<blockquote expandable>')
                    in_quote = True
                converted_lines.append(stripped[2:])  # Remove "> " prefix
            elif stripped == '>':
                if not in_quote:
                    converted_lines.append('<blockquote expandable>')
                    in_quote = True
                converted_lines.append('')  # Empty line inside quote
            else:
                if in_quote:
                    converted_lines.append('</blockquote>')
                    in_quote = False
                converted_lines.append(line)
        if in_quote:
            converted_lines.append('</blockquote>')
        raw_text = '\n'.join(converted_lines)
        
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
            '<u>', '</u>', '<ins>', '</ins>',
            '<s>', '</s>', '<strike>', '</strike>', '<del>', '</del>',
            '<tg-spoiler>', '</tg-spoiler>',
            '<blockquote>', '</blockquote>'
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
                elif tag_clean.startswith('<a ') or tag_clean.startswith('<code ') or tag_clean.startswith('<pre ') or tag_clean.startswith('<blockquote'):
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

    def _telegram_text_length(self, html_text: str) -> int:
        """Returns Telegram's caption length after parsing HTML entities and tags."""
        import re

        visible_text = re.sub(r"<[^>]+>", "", html_text)
        visible_text = html.unescape(visible_text)
        return len(visible_text.encode("utf-16-le")) // 2

    def _truncate_html_to_telegram_length(self, html_text: str, max_length: int) -> str:
        """Shortens HTML without breaking tags or Telegram's UTF-16 caption limit."""
        import re

        if self._telegram_text_length(html_text) <= max_length:
            return html_text

        result = []
        open_tags = []
        visible_length = 0
        position = 0

        while position < len(html_text):
            remainder = html_text[position:]
            tag_match = re.match(r"<[^>]+>", remainder)
            entity_match = re.match(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);", remainder)

            if tag_match:
                tag = tag_match.group(0)
                normalized_tag = tag.strip().lower()
                name_match = re.match(r"</?([a-zA-Z0-9-]+)", normalized_tag)
                name = name_match.group(1) if name_match else ""

                if normalized_tag.startswith("</"):
                    if open_tags and open_tags[-1] == name:
                        open_tags.pop()
                elif not normalized_tag.endswith("/>") and name:
                    open_tags.append(name)

                result.append(tag)
                position += len(tag)
                continue

            token = entity_match.group(0) if entity_match else html_text[position]
            token_length = len(html.unescape(token).encode("utf-16-le")) // 2
            if visible_length + token_length + 3 > max_length:
                break

            result.append(token)
            visible_length += token_length
            position += len(token)

        if position < len(html_text):
            result.append("...")

        result.extend(f"</{tag}>" for tag in reversed(open_tags))
        return "".join(result)

    def _build_photo_caption(self, title: str, text: str) -> str:
        """Builds a valid photo caption while preserving complete quote blocks."""
        import re

        formatted_title = f"<b>{self._escape_html(title)}</b>"
        formatted_text = self._format_markdown_to_html(text)
        caption = f"{formatted_title}\n\n{formatted_text}"
        if self._telegram_text_length(caption) <= 1024:
            return caption

        quote_pattern = r"<blockquote(?:\s+[^>]*)?>.*?</blockquote>"
        quotes = re.findall(quote_pattern, formatted_text, flags=re.IGNORECASE | re.DOTALL)
        if not quotes:
            return self._truncate_html_to_telegram_length(caption, 1024)

        quote_section = "\n\n".join(quotes)
        title_and_quote = f"{formatted_title}\n\n{quote_section}"
        if self._telegram_text_length(title_and_quote) > 1024:
            logger.warning("Quote exceeds Telegram's caption limit and will be shortened.")
            return self._truncate_html_to_telegram_length(title_and_quote, 1024)

        body_without_quotes = re.sub(
            quote_pattern,
            "",
            formatted_text,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()
        available_body_length = 1024 - self._telegram_text_length(title_and_quote) - 2
        shortened_body = (
            self._truncate_html_to_telegram_length(body_without_quotes, available_body_length)
            if available_body_length > 3 and body_without_quotes
            else ""
        )

        if shortened_body:
            return f"{formatted_title}\n\n{shortened_body}\n\n{quote_section}"
        return title_and_quote

    async def publish_text(self, title: str, text: str) -> bool:
        """Publishes a text post to the Telegram channel"""
        if not self.enabled:
            if self.production:
                return False
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
                    logger.error(
                        "Telegram text publish failed with status %s",
                        resp.status_code,
                    )
                    return False
        except Exception as exc:
            logger.error("Telegram text publish failed (%s)", type(exc).__name__)
            return False

    async def publish_photo(self, title: str, text: str, photo_url_or_path: str) -> bool:
        """Publishes a post with a photo/cover to the Telegram channel"""
        if not self.enabled:
            if self.production:
                return False
            logger.info(f"[DRY-RUN] Publishing photo post:\nTitle: {title}\nPhoto: {photo_url_or_path}\nText:\n{text}")
            return True

        caption = self._build_photo_caption(title, text)
        caption_length = self._telegram_text_length(caption)
        if caption_length > 1024:
            logger.error("Unable to compose a Telegram caption within the 1024-character limit.")
            return False

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
                    logger.error(
                        "Telegram photo publish failed with status %s",
                        resp.status_code,
                    )
                    return False
        except Exception as exc:
            logger.error("Telegram photo publish failed (%s)", type(exc).__name__)
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

    async def _generate_cover_title(self, title: str, text: str) -> str:
        """Generates a short, punchy 2-4 word clickbait headline in UPPERCASE specifically for the cover image"""
        prompt = f"""
Ты — профессиональный дизайнер обложек для техно-канала.
Твоя задача — придумать ультра-короткий и цепляющий заголовок (кликбейт-фразу из 2-4 слов) для картинки-обложки к посту.
Этот заголовок на картинке должен быть ДРУГИМ, более коротким и интригующим, чем заголовок самого поста.
В нем НЕ должно быть точек в конце, лишних слов (таких как "До...", "Подробнее..."), и он должен быть в UPPERCASE.

Заголовок поста: {title}
Текст поста: {text}

Верни ТОЛЬКО короткую фразу на обложку (2-4 слова) на русском языке в UPPERCASE. Никаких кавычек, объяснений или знаков препинания.
Пример:
Пост: "В Apex Legends стартовал новый ивент" -> Обложка: "КИБЕРПАНК В APEX"
"""
        try:
            from smm_engine.utils.gemini_helper import generate_content_with_retry
            from smm_engine.config import GEMINI_MODEL
            
            logger.info("Generating cover title using Gemini...")
            res = await generate_content_with_retry(
                prompt,
                initial_model=GEMINI_MODEL,
                generation_config={"temperature": 0.8}
            )
            cleaned = res.strip().replace('"', '').replace('«', '').replace('»', '').replace('.', '').upper()
            logger.info(f"Generated cover title: {cleaned}")
            return cleaned
        except Exception as e:
            logger.error(f"Failed to generate cover title: {e}")
            # Fallback: clean title and take first 4 words
            import re
            clean_t = re.sub(r'<[^>]+>', '', title)
            words = clean_t.split()
            return " ".join(words[:4]).upper()

    async def _extract_og_image(self, url: str) -> Optional[str]:
        """Fetches the news article URL and extracts the og:image or twitter:image metadata"""
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            return None
        try:
            logger.info("Extracting og:image metadata from a news URL")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            async with httpx.AsyncClient() as client:
                resp = await fetch_public_http(
                    client,
                    url,
                    headers=headers,
                    timeout=8,
                    max_bytes=2 * 1024 * 1024,
                )
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
                        logger.info("Extracted an image URL from news metadata")
                        return img_url
        except Exception as e:
            logger.warning("Failed to parse og:image metadata (%s)", type(e).__name__)
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
                if not bg_path or not bg_path.exists():
                    bg_path = None
                    
            # 4. Fallback to AI generation if no news image was found/downloaded
            if not bg_path:
                logger.info("No news image available or download failed. Falling back to AI generator...")
                keywords = await self._generate_visual_prompt(title, text)
                bg_path = await img_gen.generate_ai_background(keywords)
                    
            # 5. Generate cover title dynamically (2-4 words in UPPERCASE)
            cover_title = await self._generate_cover_title(title, text)
            
            # 6. Render final cover using the background
            cover_path = img_gen.create_cover(cover_title, bg_path)
            
            if cover_path and cover_path.exists():
                success = await self.publish_photo(title, text, str(cover_path))
                # Delete temporary cover path to save space
                try:
                    if cover_path and cover_path.exists():
                        cover_path.unlink()
                    if bg_path and bg_path.exists() and bg_path != cover_path:
                        bg_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temp cover files: {e}")
                
                if success:
                    return True
                
                logger.warning("Telegram photo publishing failed, falling back to text post...")
        except Exception as e:
            logger.error(f"Failed to publish post with cover, falling back to text: {e}")
            
        return await self.publish_text(title, text)
