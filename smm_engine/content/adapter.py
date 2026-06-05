import json
import logging
from typing import Dict, Any, Optional
import google.generativeai as genai

from smm_engine.config import GEMINI_API_KEY, STYLE_GUIDE, GEMINI_MODEL
from smm_engine.scrapers.base import NewsItem
from smm_engine.content.humanizer import TextHumanizer

logger = logging.getLogger(__name__)

class ContentAdapter:
    def __init__(self):
        self.model_name = GEMINI_MODEL
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
            final_text = f"{humanized_body}\n\n{hashtags}\n\nИсточник: {item.url}"
            
            return {
                "title": humanized_title,
                "text": final_text
            }
        except Exception as e:
            logger.error(f"Error during humanization phase: {e}")
            # Fallback to unhumanized
            return {
                "title": adapted_raw.get("title", ""),
                "text": f"{adapted_raw.get('body', '')}\n\nИсточник: {item.url}"
            }

    async def _adapt_pass(self, item: NewsItem) -> Optional[Dict[str, str]]:
        """First pass: adaptation to the target style guide"""
        style_rules = STYLE_GUIDE.get("rules", [])
        style_rules_str = "\n".join([f"- {rule}" for rule in style_rules])
        tone = STYLE_GUIDE.get("tone", {}).get("primary", "hype and gaming/tech style")
        audience = STYLE_GUIDE.get("tone", {}).get("audience", "developers, gamers, AI enthusiasts")
        
        prompt = f"""
You are the primary copywriter and SMM lead for the Telegram channel "НейроСофт Гейминг".
Target Audience: {audience}
Target Tone: {tone}

Style Rules:
{style_rules_str}

Format the following news item into an engaging, hype-filled Telegram post:
News Title: {item.title}
News URL: {item.url}
Source: {item.source}
Raw Data: {json.dumps(item.raw_data, ensure_ascii=False)}

Instructions:
1. Write in Russian.
2. Formulate a catchy, energetic title (title should NOT contain markdown bold since it will be styled separately).
3. Write the body of the post. Use short, punchy paragraphs, relevant emojis, and list points (using 🔥 as bullet points if appropriate).
4. Explain technical things simply and add some nerd humor or memey context.
5. End with an open question to encourage comments/discussion.
6. Do NOT add hashtags or the source URL to the body — those will be appended automatically later.
7. Return ONLY a JSON object in this format:
{{
  "title": "Catchy Russian Title",
  "body": "Post body text in Russian..."
}}
"""
        try:
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.7
                }
            )
            return json.loads(response.text)
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
