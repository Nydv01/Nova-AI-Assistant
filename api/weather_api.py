"""
api/weather_api.py — OpenWeatherMap integration.

Free tier key at: https://openweathermap.org/api
Set WEATHER_API_KEY in config.py or .env
"""
import logging
import requests

from config import WEATHER_API_KEY, DEFAULT_CITY

logger = logging.getLogger(__name__)
BASE_URL = "https://api.openweathermap.org/data/2.5"


class WeatherAPI:
    def __init__(self, api_key: str = WEATHER_API_KEY):
        self.api_key = api_key

    def get_current(self, city: str = DEFAULT_CITY) -> dict:
        """
        Fetch current weather for a city.
        Returns a flat dict with display-ready fields, or {"error": reason}.
        """
        if not self.api_key or self.api_key.startswith("YOUR_"):
            return self._demo_data(city)

        try:
            resp = requests.get(
                f"{BASE_URL}/weather",
                params={"q": city, "appid": self.api_key, "units": "metric"},
                timeout=8,
            )
            resp.raise_for_status()
            d = resp.json()
            return {
                "city":         d["name"],
                "country":      d["sys"]["country"],
                "temp_c":       round(d["main"]["temp"]),
                "feels_like_c": round(d["main"]["feels_like"]),
                "humidity":     d["main"]["humidity"],
                "description":  d["weather"][0]["description"],
                "wind_kmh":     round(d["wind"]["speed"] * 3.6),
                "icon":         d["weather"][0]["icon"],
            }
        except requests.exceptions.ConnectionError:
            return {"error": "No internet connection."}
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return {"error": f"City '{city}' not found."}
            if e.response.status_code == 401:
                return {"error": "Invalid API key."}
            return {"error": str(e)}
        except Exception as exc:
            logger.exception("Weather fetch failed")
            return {"error": str(exc)}

    @staticmethod
    def _demo_data(city: str) -> dict:
        """Return plausible demo data when no API key is configured."""
        import random
        conditions = [
            ("clear sky", 24, 22),
            ("partly cloudy", 19, 17),
            ("light rain", 14, 12),
            ("overcast clouds", 17, 15),
        ]
        desc, temp, feels = random.choice(conditions)
        return {
            "city":         city.title(),
            "country":      "??",
            "temp_c":       temp,
            "feels_like_c": feels,
            "humidity":     random.randint(50, 85),
            "description":  desc,
            "wind_kmh":     random.randint(5, 30),
            "icon":         "01d",
            "_demo":        True,
        }
