import difflib
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class Deduplicator:
    def __init__(self, similarity_threshold: float = 0.75):
        self.similarity_threshold = similarity_threshold

    def calculate_similarity(self, title1: str, title2: str) -> float:
        """Calculates fuzzy similarity between two titles (0.0 to 1.0)"""
        if not title1 or not title2:
            return 0.0
            
        # Normalize titles: lowercase and strip punctuation/extra spaces
        t1 = self._normalize(title1)
        t2 = self._normalize(title2)
        
        # Calculate ratio
        return difflib.SequenceMatcher(None, t1, t2).ratio()

    def _normalize(self, text: str) -> str:
        text = text.lower()
        # Remove common characters
        for char in [".", ",", "!", "?", "-", "_", ":", ";", "(", ")", "[", "]", "'", "\"", "`", "🔥", "🚀"]:
            text = text.replace(char, " ")
        # Split and rejoin to normalize whitespace
        words = [w.strip() for w in text.split() if w.strip()]
        return " ".join(words)

    def find_duplicate(self, title: str, recent_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compares title against a list of recent items, returns duplicate item if found"""
        for item in recent_items:
            # Check title similarity
            similarity = self.calculate_similarity(title, item.get("title", ""))
            if similarity >= self.similarity_threshold:
                logger.info(f"Fuzzy duplicate detected: '{title}' and '{item.get('title')}' (similarity: {similarity:.2f})")
                return item
        return None
