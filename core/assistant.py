"""
core/assistant.py — Orchestrates intent handling and produces responses.
"""
import random
import datetime
import logging
from typing import Callable, Optional

from core.intent_router import IntentRouter, Intent
from api.weather_api import WeatherAPI
from api.news_api import NewsAPI
from api.ai_chat import AIChatAPI
from storage.reminder_store import ReminderStore, Reminder

logger = logging.getLogger(__name__)


class Assistant:
    """
    Central controller: receives text, routes to the correct handler,
    and returns a (text_response, spoken_response) pair.
    """

    GREETINGS = [
        "Hello! How can I help you today?",
        "Hi there! Ready to assist. What would you like to do?",
        "Hey! I'm listening. What can I do for you?",
    ]

    JOKES = [
        "Why don't scientists trust atoms? Because they make up everything!",
        "I told my computer I needed a break. Now it won't stop sending me vacation ads.",
        "Why did the scarecrow win an award? Because he was outstanding in his field!",
        "Why can't you give Elsa a balloon? Because she'll let it go.",
        "What do you call a fish without eyes? A fsh.",
    ]

    HELP_TEXT = (
        "Here's what I can do:\n\n"
        "🌤 Weather — ask 'What's the weather in Tokyo?'\n"
        "📰 News    — ask 'Read me tech headlines'\n"
        "⏰ Remind  — say 'Remind me to call mom at 3pm'\n"
        "🕐 Time    — ask 'What time is it?'\n"
        "📅 Date    — ask 'What's the date today?'\n"
        "😄 Joke    — ask 'Tell me a joke'\n"
        "💬 Chat    — ask anything else (needs Gemini key)"
    )

    def __init__(
        self,
        on_reminder_fire: Optional[Callable[[str], None]] = None,
    ):
        self.router = IntentRouter()
        self.weather = WeatherAPI()
        self.news = NewsAPI()
        self.chat = AIChatAPI()
        self.reminders = ReminderStore(on_fire=on_reminder_fire)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def handle(self, text: str, model_source: str = "gemini", ollama_model: str = "llama3") -> tuple[str, str]:
        """
        Process user input.

        Returns:
            (display_text, spoken_text) — display_text may contain light
            markdown/emoji; spoken_text is clean plain text for TTS.
        """
        intent: Intent = self.router.classify(text)

        handlers = {
            "greeting":      self._handle_chat,
            "help":          self._handle_help,
            "time":          self._handle_time,
            "date":          self._handle_date,
            "joke":          self._handle_joke,
            "weather":       self._handle_weather,
            "news":          self._handle_news,
            "reminder":      self._handle_reminder,
            "screenshot":    self._handle_screenshot,
            "stats":         self._handle_stats,
            "media_youtube": self._handle_media_youtube,
            "media_spotify": self._handle_media_spotify,
            "chat":          self._handle_chat,
        }

        handler = handlers.get(intent.name, self._handle_chat)
        try:
            if handler == self._handle_chat:
                return self._handle_chat(intent, model_source, ollama_model)
            return handler(intent)
        except Exception as exc:
            logger.exception("Handler error for intent '%s'", intent.name)
            msg = f"Sorry, I ran into a problem: {exc}"
            return msg, msg

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_greeting(self, intent: Intent):
        msg = random.choice(self.GREETINGS)
        return msg, msg

    def _handle_help(self, intent: Intent):
        spoken = (
            "Here's what I can do: check the weather, read news headlines, "
            "set reminders, tell jokes, or have a general conversation."
        )
        return self.HELP_TEXT, spoken

    def _handle_time(self, intent: Intent):
        now = datetime.datetime.now().strftime("%I:%M %p")
        msg = f"The current time is {now}."
        return msg, msg

    def _handle_date(self, intent: Intent):
        today = datetime.date.today().strftime("%A, %B %d %Y")
        msg = f"Today is {today}."
        return msg, msg

    def _handle_joke(self, intent: Intent):
        msg = random.choice(self.JOKES)
        return msg, msg

    def _handle_weather(self, intent: Intent):
        data = self.weather.get_current(intent.city)
        if "error" in data:
            msg = f"Sorry, I couldn't get weather for {intent.city}: {data['error']}"
            return msg, msg

        display = (
            f"🌤 Weather in {data['city']}, {data['country']}\n\n"
            f"  Condition : {data['description'].capitalize()}\n"
            f"  Temperature: {data['temp_c']}°C  (feels like {data['feels_like_c']}°C)\n"
            f"  Humidity  : {data['humidity']}%\n"
            f"  Wind      : {data['wind_kmh']} km/h"
        )
        spoken = (
            f"Weather in {data['city']}: {data['description']}, "
            f"{data['temp_c']} degrees Celsius. "
            f"Feels like {data['feels_like_c']}. Humidity {data['humidity']} percent."
        )
        return display, spoken

    def _handle_news(self, intent: Intent):
        articles = self.news.get_headlines(intent.news_category)
        if not articles:
            msg = f"Sorry, I couldn't fetch {intent.news_category} headlines right now."
            return msg, msg

        lines = [f"📰 Top {intent.news_category.capitalize()} Headlines\n"]
        spoken_lines = [f"Here are the top {intent.news_category} headlines."]
        for i, a in enumerate(articles[:5], 1):
            lines.append(f"  {i}. {a['title']}")
            spoken_lines.append(f"{i}: {a['title']}.")

        return "\n".join(lines), "  ".join(spoken_lines)

    def _handle_reminder(self, intent: Intent):
        reminder = self.reminders.add(
            message=intent.reminder_msg or "Reminder",
            time_str=intent.reminder_time,
        )
        time_label = reminder.time_str or "no specific time"
        display = f"✅ Reminder set!\n\n  Message: {reminder.message}\n  Time: {time_label}"
        spoken = f"Got it! I've set a reminder for: {reminder.message}, at {time_label}."
        return display, spoken

    def _handle_chat(self, intent: Intent, model_source: str = "gemini", ollama_model: str = "llama3"):
        reply = self.chat.ask(intent.raw_text, model_source=model_source, model=ollama_model)
        return reply, reply

    def _handle_screenshot(self, intent: Intent):
        try:
            from PIL import ImageGrab
            import os
            # Grab screenshot
            screenshot = ImageGrab.grab()
            img_path = "screenshot_last.png"
            screenshot.save(img_path)
            
            # Analyze using Gemini
            prompt = (
                "You are looking at a screenshot of the user's screen. "
                "Describe what is visible concisely in 2-3 sentences. "
                "Identify the active windows, websites, or applications, and summarize the main content."
            )
            description = self.chat.ask_with_image(prompt, img_path)
            
            display = f"📸 **Screenshot Captured**\n\n{description}"
            spoken = f"Screenshot captured. Here is what I see on your screen: {description}"
            return display, spoken
        except Exception as e:
            logger.exception("Screenshot capture or analysis failed")
            err_msg = f"Failed to capture or analyze screen: {e}"
            return err_msg, err_msg

    def _handle_stats(self, intent: Intent):
        try:
            import psutil
            import subprocess
            import re
            
            # CPU Load
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # RAM Load
            ram = psutil.virtual_memory()
            ram_percent = ram.percent
            ram_gb = f"{ram.used / (1024**3):.1f}/{ram.total / (1024**3):.1f} GB"
            
            # Battery level (macOS pmset tool)
            battery_info = "Not available"
            try:
                out = subprocess.check_output(["pmset", "-g", "batt"]).decode()
                m = re.search(r"(\d+)%", out)
                if m:
                    pct = m.group(1)
                    state = "charging" if "charging" in out else "discharging"
                    if "charged" in out:
                        state = "fully charged"
                    battery_info = f"{pct}% ({state})"
            except Exception:
                pass
                
            display = (
                f"💻 **System Diagnostics**\n\n"
                f"  CPU Load : {cpu_percent}%\n"
                f"  RAM Usage: {ram_percent}% ({ram_gb})\n"
                f"  Battery  : {battery_info}"
            )
            spoken = (
                f"Your system CPU load is {cpu_percent} percent, "
                f"memory usage is {ram_percent} percent, and battery level is at {battery_info}."
            )
            return display, spoken
        except Exception as e:
            logger.exception("Failed to collect system metrics")
            err_msg = f"Failed to read system metrics: {e}"
            return err_msg, err_msg

    def _handle_media_youtube(self, intent: Intent):
        import urllib.parse
        import webbrowser
        q = intent.media_query or "synthwave"
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(q)}"
        webbrowser.open(url)
        msg = f"Opening YouTube search for: {q}"
        return msg, msg

    def _handle_media_spotify(self, intent: Intent):
        import urllib.parse
        import webbrowser
        q = intent.media_query or "synthwave"
        url = f"https://open.spotify.com/search/{urllib.parse.quote(q)}"
        webbrowser.open(url)
        msg = f"Opening Spotify search for: {q}"
        return msg, msg
