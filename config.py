"""
config.py — Central configuration and API key management.

How to set your API keys:
  Option 1 (recommended): Set environment variables before running:
      export WEATHER_API_KEY="your_openweathermap_key"
      export NEWS_API_KEY="your_newsapi_key"
      export ANTHROPIC_API_KEY="your_anthropic_key"

  Option 2: Create a .env file in the project root (auto-loaded):
      WEATHER_API_KEY=your_openweathermap_key
      NEWS_API_KEY=your_newsapi_key
      GEMINI_API_KEY=your_gemini_key

  Option 3: Edit the placeholders below directly (not recommended for shared projects).
"""
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env file if present (no extra dependencies needed)
# ---------------------------------------------------------------------------
def _load_dotenv():
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())

_load_dotenv()

# ---------------------------------------------------------------------------
# API Keys — replace placeholders or set environment variables
# ---------------------------------------------------------------------------
WEATHER_API_KEY: str = os.getenv("WEATHER_API_KEY", "YOUR_OPENWEATHERMAP_KEY_HERE")
NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "YOUR_NEWSAPI_KEY_HERE")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_KEY_HERE")

# ---------------------------------------------------------------------------
# App behaviour defaults
# ---------------------------------------------------------------------------
DEFAULT_CITY = "London"          # Fallback city for weather
NEWS_PAGE_SIZE = 5               # Number of headlines to fetch
SPEECH_RATE = 175                # Words per minute (pyttsx3)
SPEECH_VOLUME = 0.9              # 0.0 – 1.0
REMINDER_CHECK_INTERVAL = 10    # Seconds between reminder checks
APP_TITLE = "Nova AI Assistant"
APP_GEOMETRY = "900x640"

# News categories supported by NewsAPI
NEWS_CATEGORIES = ["general", "technology", "sports", "business", "science", "health", "entertainment"]

# Simple intent patterns (regex → handler name)
INTENT_PATTERNS = [
    (r"play\s+(.+?)\s+on\s+youtube|youtube\s+play\s+(.+)", "media_youtube"),
    (r"search\s+(.+?)\s+on\s+spotify|spotify\s+search\s+(.+)", "media_spotify"),
    (r"screenshot|screen shot|capture.*screen", "screenshot"),
    (r"system stats|cpu usage|ram usage|cpu|ram|battery", "stats"),
    (r"remind|reminder",            "reminder"),
    (r"weather|temperature|forecast|how (hot|cold|warm)", "weather"),
    (r"news|headline|latest.*news", "news"),
    (r"\btime\b",                   "time"),
    (r"\bdate\b",                   "date"),
    (r"joke",                       "joke"),
    (r"hello|hi |hey |what.*name|who are you", "greeting"),
    (r"help|what can you",          "help"),
]
