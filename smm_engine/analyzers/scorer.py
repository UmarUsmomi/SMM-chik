import json
import logging
from typing import Dict, Any
import google.generativeai as genai

from smm_engine.config import GEMINI_API_KEY, SCORER_MODEL
from smm_engine.scrapers.base import NewsItem

logger = logging.getLogger(__name__)

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class NewsScorer:
    def __init__(self):
        self.model_name = SCORER_MODEL
        self.enabled = bool(GEMINI_API_KEY)
        if not self.enabled:
            logger.warning("GEMINI_API_KEY is missing. Scorer will output default scores.")

    async def score_item(self, item: NewsItem) -> Dict[str, Any]:
        """Scores a news item out of 100 using Gemini Flash"""
        if not self.enabled:
            # Fallback score if API key is missing
            return {
                "relevance": 15,
                "freshness": 10,
                "virality": 10,
                "uniqueness": 10,
                "quality": 10,
                "total": 55,
                "reason": "Ключ API Gemini не настроен. Используется оценка по умолчанию."
            }

        # Construct prompt
        prompt = self._build_prompt(item)

        try:
            from smm_engine.utils.gemini_helper import generate_content_with_retry, parse_json_robust
            
            # Request JSON output
            response_text = await generate_content_with_retry(
                prompt,
                initial_model=self.model_name,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.2
                }
            )
            
            result = parse_json_robust(response_text)
            
            # Ensure all keys exist
            for key in ["relevance", "freshness", "virality", "uniqueness", "quality", "total"]:
                if key not in result:
                    result[key] = 0
            if "reason" not in result:
                result["reason"] = "No reason provided by AI."
                
            # Double check math
            sum_scores = (
                result["relevance"] + 
                result["freshness"] + 
                result["virality"] + 
                result["uniqueness"] + 
                result["quality"]
            )
            result["total"] = sum_scores
            
            logger.info(f"Scored '{item.title[:40]}...': {result['total']}/100")
            return result
            
        except Exception as e:
            logger.error(f"Error scoring item '{item.title}': {e}")
            return {
                "relevance": 0,
                "freshness": 0,
                "virality": 0,
                "uniqueness": 0,
                "quality": 0,
                "total": 0,
                "reason": f"Ошибка оценки ИИ: {str(e)}"
            }

    def _build_prompt(self, item: NewsItem) -> str:
        return f"""
Ты — профессиональный редактор Telegram-канала "НейроСофт Гейминг".
Наш канал посвящен следующим темам:
1. Искусственный интеллект (нейросети, языковые модели LLM, инструменты и модели ИИ)
2. Разработка и IT-инструменты (новые утилиты, инструменты для разработки, программирование, обновления ПО)
3. Гейминг и геймдев (обновления игр, технологии игровых движков, игровые новости, видеокарты, обновления в Steam)

Твоя задача — проанализировать следующую новость и оценить её привлекательность по 100-балльной шкале.

Заголовок новости: {item.title}
URL новости: {item.url}
Источник: {item.source}
Сырые данные/Краткое описание: {json.dumps(item.raw_data, ensure_ascii=False)}

Критерии оценки:
1. Соответствие тематике (макс. 30 баллов): Насколько хорошо новость подходит под тематику ИИ, IT-разработки или гейминга? (0 = вообще не подходит, 30 = идеальное попадание)
2. Свежесть/Актуальность (макс. 20 баллов): Насколько это горячая, важная или обсуждаемая новость прямо сейчас?
3. Вирусность (макс. 20 баллов): Насколько новость интересна и увлекательна для гиков и геймеров? Вызовет ли она желание обсудить её в комментариях?
4. Уникальность (макс. 15 баллов): Это уникальное событие/репозиторий/фича или очередная банальная статья?
5. Качество/Глубина (макс. 15 баллов): Содержит ли новость конкретные факты, ссылки на GitHub или реальное влияние на индустрию?

Ты должен ответить СТРОГО в формате JSON со следующей структурой:
{{
  "relevance": число,
  "freshness": число,
  "virality": число,
  "uniqueness": число,
  "quality": число,
  "total": число,
  "reason": "Краткое объяснение оценки строго на русском языке (1-2 предложения, объясняющие, почему эта новость актуальна и интересна для нашей аудитории гиков/геймеров)"
}}
"""
