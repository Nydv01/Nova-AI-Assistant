"""
core/intent_router.py — Map raw user text → handler name + extracted entities.
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from config import INTENT_PATTERNS

logger = logging.getLogger(__name__)


@dataclass
class Intent:
    name: str                          # e.g. "weather", "reminder", "chat"
    city: Optional[str] = None         # extracted for weather
    reminder_msg: Optional[str] = None
    reminder_time: Optional[str] = None
    news_category: str = "general"
    media_query: Optional[str] = None  # extracted for media
    raw_text: str = ""


class IntentRouter:
    """
    Rule-based intent classifier.  Falls back to 'chat' for anything
    that doesn't match a known pattern.
    """

    NEWS_CAT_MAP = {
        "tech": "technology", "technology": "technology",
        "sport": "sports", "sports": "sports",
        "business": "business", "finance": "business",
        "science": "science", "health": "health",
        "entertainment": "entertainment", "world": "general",
    }

    def classify(self, text: str) -> Intent:
        lower = text.lower().strip()
        intent = Intent(name="chat", raw_text=text)

        for pattern, handler in INTENT_PATTERNS:
            if re.search(pattern, lower):
                intent.name = handler
                break

        # Entity extraction per intent
        if intent.name == "weather":
            intent.city = self._extract_city(lower)
        elif intent.name == "reminder":
            intent.reminder_msg, intent.reminder_time = self._extract_reminder(lower)
        elif intent.name == "news":
            intent.news_category = self._extract_news_category(lower)
        elif intent.name in ("media_youtube", "media_spotify"):
            intent.media_query = self._extract_media_query(lower, intent.name)

        logger.debug("Intent: %s | text=%r", intent.name, text[:60])
        return intent

    # ------------------------------------------------------------------
    # Entity extractors
    # ------------------------------------------------------------------

    def _extract_media_query(self, text: str, name: str) -> Optional[str]:
        for pattern, handler in INTENT_PATTERNS:
            if handler == name:
                m = re.search(pattern, text)
                if m:
                    for g in m.groups():
                        if g is not None and g.strip():
                            return g.strip()
        return None

    def _extract_city(self, text: str) -> str:
        from config import DEFAULT_CITY
        # "weather in Paris", "weather for New York", "temperature at Tokyo"
        m = re.search(r"(?:in|for|at)\s+([a-zA-Z\s]{2,25})(?:\?|$|,)", text)
        if m:
            return m.group(1).strip().title()
        return DEFAULT_CITY

    def _extract_reminder(self, text: str) -> tuple[str, Optional[str]]:
        # Extract time component
        time_match = re.search(
            r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
            text, re.IGNORECASE
        )
        time_str = None
        if time_match:
            h = int(time_match.group(1))
            m = int(time_match.group(2) or 0)
            ap = (time_match.group(3) or "").lower()
            if ap == "pm" and h < 12:
                h += 12
            if ap == "am" and h == 12:
                h = 0
            time_str = f"{h:02d}:{m:02d}"

        # Extract message: strip trigger words and time phrases
        msg = re.sub(r"remind(er)?\s+(me\s+)?", "", text, flags=re.IGNORECASE)
        msg = re.sub(r"\bat\s+\d{1,2}(:\d{2})?\s*(am|pm)?", "", msg, flags=re.IGNORECASE)
        msg = re.sub(r"\bto\s+", "", msg, count=1)
        msg = msg.strip(" ,?.")
        if not msg:
            msg = "Reminder"

        return msg.capitalize(), time_str

    def _extract_news_category(self, text: str) -> str:
        for keyword, category in self.NEWS_CAT_MAP.items():
            if keyword in text:
                return category
        return "general"
