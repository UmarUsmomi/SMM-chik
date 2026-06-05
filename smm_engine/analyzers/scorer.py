import json
import logging
from typing import Dict, Any
import google.generativeai as genai

from smm_engine.config import GEMINI_API_KEY
from smm_engine.scrapers.base import NewsItem

logger = logging.getLogger(__name__)

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class NewsScorer:
    def __init__(self):
        self.model_name = "gemini-1.5-flash" # Default free tier model
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
                "reason": "Gemini API key not configured. Using default safety score."
            }

        # Construct prompt
        prompt = self._build_prompt(item)

        try:
            model = genai.GenerativeModel(self.model_name)
            
            # Request JSON output
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.2
                }
            )
            
            result = json.loads(response.text)
            
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
                "reason": f"AI scoring failed: {str(e)}"
            }

    def _build_prompt(self, item: NewsItem) -> str:
        return f"""
You are an expert editor for the Telegram channel "НейроСофт Гейминг".
The channel covers:
1. Artificial Intelligence (Neural Networks, LLMs, AI tools, AI models)
2. Software & Tech Tools (new utilities, coding tools, programming, software updates)
3. Gaming & Game Dev (game updates, game engine tech, gaming news, gaming GPUs, Steam updates)

Your task is to analyze the following news item and score it out of 100 points.

News Title: {item.title}
News URL: {item.url}
Source: {item.source}
Raw Meta/Summary: {json.dumps(item.raw_data, ensure_ascii=False)}

Score criteria:
1. Relevance (max 30 pts): How well does it fit AI, Software, or Gaming? (0 = totally unrelated, 30 = perfect fit)
2. Freshness/Hotness (max 20 pts): Is it an urgent, hot, or highly active news?
3. Virality (max 20 pts): How engaging or hype-worthy is this for tech geeks and gamers? Does it make people want to comment?
4. Uniqueness (max 15 pts): Is this a unique event/repo/feature, or just another generic blog post?
5. Quality/Depth (max 15 pts): Does the source/text have concrete facts, github links, or real-world impact?

You must respond ONLY with a JSON object in this format:
{{
  "relevance": number,
  "freshness": number,
  "virality": number,
  "uniqueness": number,
  "quality": number,
  "total": number,
  "reason": "Brief English or Russian explanation of the score"
}}
"""
