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
4. IMPORTANT: Maintain and preserve all HTML formatting tags such as <b>...</b>, <i>...</i>, and <blockquote expandable>...</blockquote> exactly as they are. Do NOT strip or corrupt these tags.
5. If the text is already good and has no AI-isms, return it as is. Do NOT add new details.
6. Return ONLY the final cleaned text, without any explanations or meta-comments.
7. IMPORTANT: If the input text is a title/heading written in UPPERCASE, preserve the UPPERCASE formatting (do not convert it to lowercase or sentence case).
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
                return cleaned_text
            return text
        except Exception as e:
            logger.error(f"Error humanizing text: {e}")
            return text
