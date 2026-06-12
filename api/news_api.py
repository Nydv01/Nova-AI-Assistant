"""
api/news_api.py — NewsAPI.org integration.

Free key (100 requests/day) at: https://newsapi.org
Set NEWS_API_KEY in config.py or .env
"""
import logging
import requests

from config import NEWS_API_KEY, NEWS_PAGE_SIZE

logger = logging.getLogger(__name__)
BASE_URL = "https://newsapi.org/v2"


class NewsAPI:
    def __init__(self, api_key: str = NEWS_API_KEY):
        self.api_key = api_key

    def get_headlines(self, category: str = "general", country: str = "us") -> list[dict]:
        """
        Return a list of headline dicts: [{"title": ..., "source": ..., "url": ...}]
        Returns demo headlines if no API key is configured.
        """
        if not self.api_key or self.api_key.startswith("YOUR_"):
            return self._demo_headlines(category)

        try:
            resp = requests.get(
                f"{BASE_URL}/top-headlines",
                params={
                    "category": category,
                    "country":  country,
                    "pageSize": NEWS_PAGE_SIZE,
                    "apiKey":   self.api_key,
                },
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "title":  a.get("title", "No title"),
                    "source": a.get("source", {}).get("name", "Unknown"),
                    "url":    a.get("url", ""),
                }
                for a in data.get("articles", [])
                if a.get("title") and "[Removed]" not in a.get("title", "")
            ]
        except requests.exceptions.ConnectionError:
            logger.warning("No internet connection for news.")
            return []
        except Exception as exc:
            logger.exception("News fetch failed")
            return []

    @staticmethod
    def _demo_headlines(category: str) -> list[dict]:
        headlines_by_cat = {
            "general": [
                "World leaders gather for climate summit in Geneva",
                "Global markets rise after positive economic data",
                "Scientists make breakthrough in renewable energy storage",
            ],
            "technology": [
                "New AI models set records on reasoning benchmarks",
                "Major tech firm unveils next-generation chip architecture",
                "Startup raises $500M to build quantum computing platform",
            ],
            "sports": [
                "Champions League final draws record television audience",
                "Athletics world record broken at international meet",
                "New signing reshapes title race ahead of crucial season",
            ],
            "business": [
                "Central bank holds rates steady amid mixed signals",
                "Retail giant reports record quarterly profit",
                "Merger talks between two industry leaders confirmed",
            ],
            "science": [
                "James Webb telescope captures earliest galaxy ever observed",
                "New study links gut bacteria to cognitive performance",
                "Researchers decode ancient manuscript using machine learning",
            ],
        }
        rows = headlines_by_cat.get(category, headlines_by_cat["general"])
        return [{"title": t, "source": "Demo Feed", "url": ""} for t in rows]
