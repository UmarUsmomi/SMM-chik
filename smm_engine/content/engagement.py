import httpx
import logging
from typing import Optional, Dict
import google.generativeai as genai

from smm_engine.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

class EngagementGenerator:
    def __init__(self):
        self.enabled = bool(GEMINI_API_KEY)
        self.model_name = GEMINI_MODEL

    async def get_programming_joke(self) -> Optional[str]:
        """Fetches a programming joke and translates it to funny Russian using Gemini"""
        url = "https://v2.jokeapi.dev/joke/Programming?safe-mode"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    
                    if data.get("type") == "single":
                        joke_text = data.get("joke")
                    else:
                        joke_text = f"{data.get('setup')}\n\n... {data.get('delivery')}"
                        
                    if not joke_text:
                        return None
                        
                    # Translate/Adapt with Gemini
                    adapted_joke = await self._translate_and_spice_joke(joke_text)
                    return adapted_joke
        except Exception as e:
            logger.error(f"Error fetching/translating joke: {e}")
            
        return "Почему программисты предпочитают темную тему? Потому что свет притягивает багов! 💻" # default fallback

    async def get_tech_quote(self) -> Optional[str]:
        """Fetches a technology quote and translates it to Russian"""
        url = "https://api.quotable.io/random?tags=technology|science"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    quote = data.get("content")
                    author = data.get("author")
                    
                    if not quote:
                        return None
                        
                    adapted_quote = await self._translate_quote(quote, author)
                    return adapted_quote
        except Exception as e:
            logger.error(f"Error fetching/translating quote: {e}")
            
        return "«Технологии — это просто инструменты. Люди — вот что действительно важно.» — Стив Джобс" # fallback

    async def _translate_and_spice_joke(self, english_joke: str) -> str:
        if not self.enabled:
            return f"[Eng Joke] {english_joke}"
            
        prompt = f"""
Translate and adapt this English programmer joke into Russian.
Make it sound extremely funny, natural, and use Russian developer/gaming slang where appropriate (e.g. 'прод', 'баг', 'код', 'джун', 'костыль').
Do not translate literally word-by-word if it ruins the punchline; instead, make a funny adaptation.

Joke:
"{english_joke}"

Return ONLY the adapted Russian joke text. No extra text or explanations.
"""
        try:
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(prompt, generation_config={"temperature": 0.8})
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini joke adaptation error: {e}")
            return english_joke

    async def _translate_quote(self, quote: str, author: str) -> str:
        if not self.enabled:
            return f"«{quote}» — {author}"
            
        prompt = f"""
Translate this quote about technology/science to Russian. Keep it wise, accurate, and inspiring.

Quote: "{quote}"
Author: {author}

Format the output as: «Текст цитаты» — Автор

Return ONLY the formatted Russian quote. No extra text or explanations.
"""
        try:
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(prompt, generation_config={"temperature": 0.3})
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini quote translation error: {e}")
            return f"«{quote}» — {author}"
