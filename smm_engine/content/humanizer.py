import logging
import google.generativeai as genai

from smm_engine.config import GEMINI_API_KEY, HUMANIZER_MODEL

logger = logging.getLogger(__name__)

# 30 patterns of AI writing (humanizer rules)
HUMANIZER_RULES = """
Below are the 30 patterns of AI-written text that you MUST detect and fix. If you see any of these, rewrite the sentences to sound like an authentic human tech-blogger:

### CONTENT LEVEL PATTERNS
1. Overblown significance: "marking a pivotal moment", "groundbreaking", "revolutionary shift". (Instead, describe what it does).
2. Cliché "challenges": "Despite challenges, it continues to thrive".
3. Intrusive prominence: Over-citing popular media to sound important ("cited in NYT, BBC...").
4. "Reflective" analysis: ending sentences with -ing clauses ("symbolizing...", "reflecting...", "showcasing...").
5. Hype marketing speech: "nestled within...", "seamlessly integrates...", "game changer".
6. Vague attributions: "Experts believe...", "Critics say...".

### LANGUAGE LEVEL PATTERNS
7. AI Vocabulary: Words like "delve", "enhance", "tapestry", "landscape", "underscore", "testament", "pivotal", "catalyst", "beacon".
8. Avoiding "is" or simple verbs: Overusing "serves as", "stands as", "boasts", "exhibits".
9. False ranges: "from the Big Bang to dark matter" (over-exaggerated lists).
10. Negative parallelisms: "It's not just a tool, it's a way of life".
11. Rule of Three: Triplets of words like "innovation, inspiration, and insights".
12. Passive voice: "Configuration is completed easily" -> "Just configure it".
13. Synonyms cycle: cycling through synonyms of the main subject to avoid repetition (AI -> system -> platform -> engine -> tool).

### STYLE LEVEL PATTERNS
14. Dash abuse: Overusing dashes (—) for parenthetical thoughts.
15. Bold text overuse: bolding every key phrase or word.
16. Title Case: capitalizing every word in headings.
17. Structured lists where prose is better.

### RUSSIAN AI-ISMS (CRITICAL)
18. "Следует отметить", "Нельзя не отметить", "Безусловно", "Конечно".
19. "В мире, где...", "В современную эпоху...", "В век цифровых технологий...".
20. "Давайте разберёмся", "Давайте погрузимся".
21. "Это подчёркивает", "Что подчёркивает значимость".
22. "Ключевой аспект", "Ключевую роль".
23. "Тем не менее", "Однако".
24. "Всё более актуальным", "Становится всё более популярным".
25. "Оставляет неизгладимый след".
26. "По мнению экспертов", "Специалисты сходятся во мнении".
27. "Уникальное сочетание...", "Уникальный инструмент".
28. "Является отличным примером того, как...".
29. "Стоит обратить внимание на...".
30. "Раздвигает границы возможного".
"""

class TextHumanizer:
    def __init__(self):
        self.model_name = HUMANIZER_MODEL
        self.enabled = bool(GEMINI_API_KEY)

    async def humanize(self, text: str) -> str:
        """Runs the second pass of generation to clean the text from AI-isms"""
        if not self.enabled or not text:
            return text

        prompt = f"""
You are a professional human editor. Your task is to clean up a tech blog post from "AI-isms" (clichés, words, and styles that AI writers commonly use).

Here are the 30 rules/patterns to look out for:
{HUMANIZER_RULES}

Input text to clean:
---
{text}
---

Instructions:
1. Identify and remove any AI-isms, cliches, or unnatural language.
2. Rewrite sentences to be simple, human, and direct. Keep the hype/energetic/cool tone but make it sound like a real human wrote it.
3. Keep it in Russian.
4. IMPORTANT: Do NOT use any HTML tags EXCEPT for blockquote. You may use <blockquote expandable>цитата</blockquote> to wrap real quotes. Strictly no <p>, <div>, or any other tags. Use standard markdown **bold** for emphasis.
5. If the text is already good and has no AI-isms, return it as is. Do NOT add new details.
6. Return ONLY the final cleaned text, without any explanations or meta-comments.
7. IMPORTANT: Do NOT use `*` or `-` for bullet points. Keep the emoji bullets (e.g. 🤖 — текст) exactly as they were provided.
8. IMPORTANT: Keep the final text strictly under 400 characters to ensure it fits social media limits. Make sure the text is logically complete and ends with a complete sentence.
"""

        try:
            from smm_engine.utils.gemini_helper import generate_content_with_retry
            response_text = await generate_content_with_retry(
                prompt,
                initial_model=self.model_name,
                generation_config={"temperature": 0.1}
            )
            cleaned_text = response_text.strip()
            if cleaned_text:
                # Post-sanitize: remove any stray markdown artifacts that reveal AI origin
                import re
                # Remove markdown headers
                cleaned_text = re.sub(r'^#{1,6}\s+', '', cleaned_text, flags=re.MULTILINE)
                # Remove single asterisks not part of **bold**
                cleaned_text = re.sub(r'(?<!\*)\*(?!\*)', '', cleaned_text)
                # Remove dash bullets at line start
                cleaned_text = re.sub(r'^[\-]\s+', '🔹 ', cleaned_text, flags=re.MULTILINE)
                # Remove excessive separator lines
                cleaned_text = re.sub(r'\n-{3,}\n', '\n', cleaned_text)
                # Collapse multiple spaces
                cleaned_text = re.sub(r' +', ' ', cleaned_text)
                return cleaned_text.strip()
            return text
        except Exception as e:
            logger.error(f"Error humanizing text: {e}")
            return text
