import json
import logging
from typing import Dict, Any, Optional
import google.generativeai as genai

from smm_engine.config import GEMINI_API_KEY, STYLE_GUIDE, ADAPTER_MODEL
from smm_engine.scrapers.base import NewsItem
from smm_engine.content.humanizer import TextHumanizer
from smm_engine.utils.gemini_helper import generate_content_with_retry, parse_json_robust

logger = logging.getLogger(__name__)

class ContentAdapter:
    def __init__(self):
        self.model_name = ADAPTER_MODEL
        self.enabled = bool(GEMINI_API_KEY)
        self.humanizer = TextHumanizer()

    async def adapt_news(self, item: NewsItem) -> Optional[Dict[str, str]]:
        """Adapts news item to the channel's style and humanizes it"""
        if not self.enabled:
            return {
                "title": f"[MVP Mode] {item.title}",
                "text": f"Новость от {item.source}: {item.title}\n\nПодробности по ссылке: {item.url}"
            }

        # 1. Adapt Content (Pass 1)
        adapted_raw = await self._adapt_pass(item)
        if not adapted_raw:
            return None

        # 2. Humanize Content (Pass 2)
        try:
            logger.info(f"Running humanizer on adapted content for '{item.title[:30]}...'")
            humanized_title = await self.humanizer.humanize(adapted_raw.get("title", ""), is_title=True)
            
            # Preserve blockquotes through humanizer by extracting them first
            import re
            body_raw = adapted_raw.get("body", "")
            blockquote_pattern = r'(<blockquote[^>]*>.*?</blockquote>)'
            blockquotes = re.findall(blockquote_pattern, body_raw, re.DOTALL)
            
            # Replace each with [QUOTE_0], [QUOTE_1], etc.
            body_without_quotes = body_raw
            for idx, bq in enumerate(blockquotes):
                body_without_quotes = body_without_quotes.replace(bq, f'[QUOTE_{idx}]', 1)
            
            humanized_body = await self.humanizer.humanize(body_without_quotes)
            
            # Re-insert preserved blockquotes
            for idx, bq in enumerate(blockquotes):
                humanized_body = humanized_body.replace(f'[QUOTE_{idx}]', bq, 1)
            # Remove any remaining placeholders if humanizer swallowed them
            for idx in range(len(blockquotes)):
                humanized_body = humanized_body.replace(f'[QUOTE_{idx}]', '')
            
            if '<blockquote' in body_raw and '<blockquote' not in humanized_body:
                logger.warning(f"Blockquote was LOST during humanization for '{item.title[:30]}...'")
            elif '<blockquote' in humanized_body:
                logger.info(f"Blockquote survived humanization for '{item.title[:30]}...'")
            
            # Combine body and tags if needed, or format as final post text
            hashtags = self._generate_hashtags(item.source, item.raw_data.get("tags", []))
            final_text = f"{humanized_body}\n\n{hashtags}".strip()
            
            # Sanitize markdown artifacts that reveal AI origin
            final_text = self._sanitize_ai_text(final_text)
            humanized_title = self._sanitize_ai_text(humanized_title)
            
            # Validation: check for empty or literal 'None' string (common AI error under rate limit/blocks)
            if not humanized_title or not humanized_body:
                return None
                
            title_stripped = humanized_title.strip()
            body_stripped = humanized_body.strip()
            
            if title_stripped.lower() == "none" or body_stripped.lower() == "none":
                logger.warning(f"Content adapter returned literal 'None' string for '{item.title[:30]}...'. Treating as failed adaptation.")
                return None
            
            return {
                "title": title_stripped,
                "text": final_text
            }
        except Exception as e:
            logger.error(f"Error during humanization phase: {e}")
            # Fallback to unhumanized
            raw_title = adapted_raw.get("title", "")
            raw_body = adapted_raw.get("body", "")
            if not raw_title or not raw_body or raw_title.strip().lower() == "none" or raw_body.strip().lower() == "none":
                return None
            return {
                "title": raw_title.strip(),
                "text": f"{raw_body.strip()}\n\n{self._generate_hashtags(item.source, item.raw_data.get('tags', []))}".strip()
            }

    async def _adapt_pass(self, item: NewsItem) -> Optional[Dict[str, str]]:
        """First pass: adaptation to the target style guide"""
        style_rules = STYLE_GUIDE.get("rules", [])
        style_rules_str = "\n".join([f"- {rule}" for rule in style_rules])
        tone = STYLE_GUIDE.get("tone", {}).get("primary", "хайповый, энергичный, мемный, но интеллектуальный")
        audience = STYLE_GUIDE.get("tone", {}).get("audience", "разработчики, геймеры, гики, энтузиасты ИИ")
        
        formatting = STYLE_GUIDE.get("formatting", {})
        max_length = formatting.get("max_length", 400)
        
        content_str = item.raw_data.get("content") or item.raw_data.get("description") or item.raw_data.get("summary") or ""
        is_long = len(content_str) > 500
        
        # Check if content has a direct quote (in Cyrillic or Latin) to force allow it, otherwise keep random for tests
        has_direct_quote = any(q in content_str for q in ['"', '«', '»', '“', '”'])
        import random
        allow_blockquote = is_long and (has_direct_quote or (random.random() < 0.60))
        
        if allow_blockquote:
            blockquote_instruction = "- Если в новости есть яркая прямая цитата эксперта, руководителя или разработчика, ОБЯЗАТЕЛЬНО оформи её тегом <blockquote expandable>текст цитаты</blockquote>. Цитаты делают пост живее и интереснее. Не придумывай цитаты — перефразируй реальные слова из источника."
        else:
            blockquote_instruction = "- КАТЕГОРИЧЕСКИ ЗАПРЕЩАЕТСЯ использовать тег <blockquote> или <blockquote expandable> в этом посте. Все цитаты должны быть перефразированы простым текстом."
            
        prompt = f"""
Ты — ведущий копирайтер Telegram-канала "НейроСофт Гейминг".
Целевая аудитория: {audience}
Тональность: {tone}

ФОРМАТ ПОСТА (СТРОГО):
1. Введение: Самая главная мысль или суть новости (одно-два предложения). Пиши без лишних HTML-тегов (никаких <p> и т.д.).
2. Основные пункты: Краткий маркированный список. ВМЕСТО звездочек или тире используй подходящие по смыслу эмодзи, за которыми следует тире (например: 🤖 — текст). Ключевые слова выделяй **жирным** шрифтом (две звездочки).
3. Заключительный вопрос: Закончи пост одним вовлекающим вопросом с эмодзи 💬.

СТРОГИЕ ПРАВИЛА:
{style_rules_str}
- Длина всего поста: СТРОГО до {max_length} символов! Пиши максимально емко.
{blockquote_instruction}
- Пост должен оканчиваться логически завершенным предложением, без обрезки на полуслове.
- НЕ используй хэштеги — они запрещены.
- В списках КАТЕГОРИЧЕСКИ ЗАПРЕЩАЕТСЯ использовать символ `*` для маркеров! Только эмодзи!

Новость для адаптации:
Заголовок: {item.title}
Источник: {item.source}
Данные: {json.dumps(item.raw_data, ensure_ascii=False)[:500]}

Верни СТРОГО JSON:
{{
  "title": "ЗАГОЛОВОК С ЭМОДЗИ В UPPERCASE",
  "body": "Структурированный текст поста (введение, пункты с эмодзи 🤖 —, вопрос 💬)"
}}
"""
        try:
            response_text = await generate_content_with_retry(
                prompt,
                initial_model=self.model_name,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.7
                }
            )
            return parse_json_robust(response_text)
        except Exception as e:
            logger.error(f"Error in adaptation pass: {e}")
            return None

    def _generate_hashtags(self, source: str, tags: list) -> str:
        """Disabled: Hashtags are no longer used based on new design"""
        return ""

    def _sanitize_ai_text(self, text: str) -> str:
        """Removes markdown artifacts that make text look AI-generated."""
        import re
        if not text:
            return text

        # Remove markdown headers (#, ##, ###)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

        # Remove single asterisks used as bullet markers (but keep **bold**)
        # Replace lines starting with * or - followed by space with emoji bullet
        text = re.sub(r'^[\*\-]\s+', '🔹 ', text, flags=re.MULTILINE)
        # Remove any remaining stray single asterisks not part of **bold**
        text = re.sub(r'(?<!\*)\*(?!\*)', '', text)

        # Remove markdown tables and code blocks (rare but possible)
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'\|.*\|', '', text)

        # Remove excessive dashes used as separators
        text = re.sub(r'\n-{3,}\n', '\n', text)

        # Remove leading/trailing whitespace per line and collapse multiple spaces
        lines = [line.strip() for line in text.splitlines()]
        text = '\n'.join(lines)
        text = re.sub(r' +', ' ', text)

        return text.strip()
