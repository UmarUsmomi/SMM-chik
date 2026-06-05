import httpx
import logging
import json
import random
from typing import Dict, Any, Optional
import google.generativeai as genai

from smm_engine.config import IMGFLIP_USERNAME, IMGFLIP_PASSWORD, GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Standard popular meme templates
POPULAR_MEMES = {
    "drake": {"id": "181913649", "name": "Drake Hotline Bling", "desc": "Top panel: something bad/lame (refusing). Bottom panel: something cool/AI/nerdy (accepting)."},
    "distracted": {"id": "112126291", "name": "Distracted Boyfriend", "desc": "Boyfriend (tech developer), looking at hot girl (new AI tool/feature), girlfriend (current stack/standard framework) looking annoyed."},
    "button": {"id": "87743020", "name": "Two Buttons", "desc": "Two buttons to press. Left button: bad choice (e.g. fix bug). Right button: funny choice (e.g. rewrite code in Rust/run AI)."},
    "brain": {"id": "93895088", "name": "Expanding Brain", "desc": "Four panels. Panel 1: basic idea. Panel 2: slightly better. Panel 3: genius tech idea. Panel 4: absolute absurd/funny nerd idea."}
}

class MemeMaker:
    def __init__(self):
        self.username = IMGFLIP_USERNAME
        self.password = IMGFLIP_PASSWORD
        self.enabled = bool(self.username and self.password and GEMINI_API_KEY)
        if not self.enabled:
            logger.warning("Imgflip credentials or Gemini API key missing. Meme Maker is running in dry-run mode.")

    async def create_meme_for_news(self, news_title: str) -> Optional[str]:
        """Generates a meme image URL based on news topic using Gemini and Imgflip API"""
        if not self.enabled:
            logger.info("[DRY-RUN] Generating meme caption for news: " + news_title)
            return "https://i.imgflip.com/30b1gx.jpg" # Drake meme placeholder for testing

        # 1. Pick a random template
        meme_key = random.choice(list(POPULAR_MEMES.keys()))
        template = POPULAR_MEMES[meme_key]
        
        # 2. Get captions from Gemini
        captions = await self._generate_captions(news_title, template)
        if not captions:
            return None

        # 3. Request captioned image from Imgflip
        url = "https://api.imgflip.com/caption_image"
        payload = {
            "template_id": template["id"],
            "username": self.username,
            "password": self.password,
            "text0": captions.get("text0", ""),
            "text1": captions.get("text1", "")
        }
        
        # For templates with 3 or more boxes, we can add boxes
        if "text2" in captions:
            payload["text2"] = captions["text2"]
        if "text3" in captions:
            payload["text3"] = captions["text3"]

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, data=payload, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        meme_url = data["data"]["url"]
                        logger.info(f"Meme generated: {meme_url} using template '{template['name']}'")
                        return meme_url
                    else:
                        logger.error(f"Imgflip error: {data.get('error_message')}")
                else:
                    logger.error(f"Imgflip HTTP error: {resp.status_code}")
        except Exception as e:
            logger.error(f"Error calling Imgflip API: {e}")
            
        return None

    async def _generate_captions(self, news_title: str, template: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Asks Gemini to write funny captions matching the selected meme template"""
        prompt = f"""
You are a witty tech SMM manager. Your task is to write caption text for a meme template based on this news:
News Topic: "{news_title}"

Meme Template: "{template['name']}"
Description of template style: {template['desc']}

Write the texts for the meme panels.
- For Drake (2 panels): text0 is top panel (bad/lame), text1 is bottom panel (cool/nerdy).
- For Distracted Boyfriend (3 panels): text0 is hot girl (new thing), text1 is boyfriend (developers), text2 is girlfriend (old thing).
- For Two Buttons (2 panels): text0 is button 1 (normal choice), text1 is button 2 (nerdy choice).
- For Expanding Brain (4 panels): text0 (basic), text1 (smarter), text2 (genius), text3 (absurd/funny).

Keep the texts VERY short (under 5-6 words per panel) and in Russian.
Write it in simple, direct, developer-slang Russian (using words like 'код', 'баг', 'прод', 'нейронка', 'гейминг').

Return ONLY a JSON object:
{{
  "text0": "text for box 0",
  "text1": "text for box 1",
  "text2": "optional text for box 2",
  "text3": "optional text for box 3"
}}
"""
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.9
                }
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Error generating meme captions: {e}")
            return None
