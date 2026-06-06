import json
import logging
from typing import Dict, Any, Optional
import google.generativeai as genai

from smm_engine.config import GEMINI_API_KEY, STYLE_GUIDE, ADAPTER_MODEL
from smm_engine.scrapers.base import NewsItem
from smm_engine.content.humanizer import TextHumanizer

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
            humanized_title = await self.humanizer.humanize(adapted_raw.get("title", ""))
            humanized_body = await self.humanizer.humanize(adapted_raw.get("body", ""))
            
            # Combine body and tags if needed, or format as final post text
            hashtags = self._generate_hashtags(item.source, item.raw_data.get("tags", []))
            final_text = f"{humanized_body}\n\n{hashtags}"
            
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
                "text": f"{raw_body.strip()}\n\n{self._generate_hashtags(item.source, item.raw_data.get('tags', []))}"
            }

    async def _adapt_pass(self, item: NewsItem) -> Optional[Dict[str, str]]:
        """First pass: adaptation to the target style guide"""
        style_rules = STYLE_GUIDE.get("rules", [])
        style_rules_str = "\n".join([f"- {rule}" for rule in style_rules])
        tone = STYLE_GUIDE.get("tone", {}).get("primary", "хайповый, энергичный, мемный, но интеллектуальный")
        audience = STYLE_GUIDE.get("tone", {}).get("audience", "разработчики, геймеры, гики, энтузиасты ИИ")
        
        formatting = STYLE_GUIDE.get("formatting", {})
        max_length = formatting.get("max_length", 500)
        
        prompt = f"""
Ты — ведущий копирайтер Telegram-канала "НейроСофт Гейминг".
Целевая аудитория: {audience}
Тональность: {tone}

ФОРМАТ ПОСТА (СТРОГО):
1. Заголовок: Тематический эмодзи + UPPERCASE. Пример: "⚡ GEMMA 2: НОВАЯ ЭРА ИИ"
2. Тело: 2-3 коротких предложения. Что случилось, почему это важно. Ключевые слова выдели <b>жирным</b>.
3. Вопрос: Закончи одним вовлекающим вопросом.

СТРОГИЕ ПРАВИЛА:
{style_rules_str}
- Длина body: СТРОГО до {max_length} символов! Пиши кратко и по делу.
- НЕ используй <blockquote> и списки — пиши только прозу.
- НЕ используй маркеры 🔥 для списков.
- НЕ добавляй хэштеги — они добавятся автоматически.

Новость для адаптации:
Заголовок: {item.title}
Источник: {item.source}
Данные: {json.dumps(item.raw_data, ensure_ascii=False)[:500]}

Верни СТРОГО JSON:
{{
  "title": "ЗАГОЛОВОК С ЭМОДЗИ В UPPERCASE",
  "body": "Краткое тело поста (2-3 предложения + вопрос)"
}}
"""
        try:
            from smm_engine.utils.gemini_helper import generate_content_with_retry
            response_text = await generate_content_with_retry(
                prompt,
                initial_model=self.model_name,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.7
                }
            )
            return json.loads(response_text)
        except Exception as e:
            logger.error(f"Error in adaptation pass: {e}")
            return None

    def _generate_hashtags(self, source: str, tags: list) -> str:
        """Generates standard hashtags based on channel guidelines"""
        # Get tags from style guide
        hashtag_config = STYLE_GUIDE.get("hashtags", {})
        
        selected = set()
        
        # Add basic tags based on source/type
        if source == "steam" or "gaming" in tags or "gamedev" in tags:
            selected.update(hashtag_config.get("gaming", ["#гейминг", "#игры"]))
        elif source == "github" or "devto" in source:
            selected.update(hashtag_config.get("software", ["#разработка", "#программирование"]))
        else:
            # default AI tags
            selected.update(hashtag_config.get("ai", ["#ии", "#нейросети"]))
            
        # Limit hashtags
        max_hashtags = STYLE_GUIDE.get("formatting", {}).get("max_hashtags", 3)
        return " ".join(list(selected)[:max_hashtags])
