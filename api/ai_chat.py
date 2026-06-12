"""
api/ai_chat.py — Google Gemini API for general conversational responses (free tier).

Get a free API key at: https://aistudio.google.com/
Set GEMINI_API_KEY in config.py or .env
"""
import logging
import requests

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a friendly voice assistant. Keep replies concise — two or three sentences "
    "maximum — because your responses will be read aloud. Be warm, helpful, and natural. "
    "Avoid markdown formatting since the output is spoken."
)


class AIChatAPI:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.api_key = api_key
        self._history: list[dict] = []   # rolling conversation context

    def ask(self, text: str) -> str:
        """
        Send a message to Google Gemini and return the reply.
        Falls back to a polite placeholder if no key is configured.
        """
        if not self.api_key or self.api_key.startswith("YOUR_"):
            return (
                "I'd be happy to chat! For open-ended conversations, "
                "please add your Gemini API key to the .env file. "
                "You can get one for free at Google AI Studio."
            )

        self._history.append({"role": "user", "content": text})

        # Map history to Gemini's format: roles are "user" and "model"
        contents = []
        for msg in self._history[-10:]:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
            resp = requests.post(
                url,
                headers={"content-type": "application/json"},
                json={
                    "contents": contents,
                    "systemInstruction": {
                        "parts": [{"text": SYSTEM_PROMPT}]
                    },
                    "generationConfig": {
                        "maxOutputTokens": 300,
                        "temperature": 0.7
                    }
                },
                timeout=15,
            )
            resp.raise_for_status()
            
            # Parse Gemini response
            resp_data = resp.json()
            reply = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            self._history.append({"role": "assistant", "content": reply})
            return reply

        except requests.exceptions.ConnectionError:
            return "I can't reach the internet right now. Please check your connection."
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 400:
                # Check for API key invalid error
                try:
                    err_msg = exc.response.json().get("error", {}).get("message", "")
                    if "API key not valid" in err_msg:
                        return "The Gemini API key looks incorrect. Please check it in config.py or .env."
                except Exception:
                    pass
            logger.exception("Gemini API error")
            return f"AI service error ({exc.response.status_code}). Please try again."
        except Exception as exc:
            logger.exception("Chat API unexpected error")
            return "Something went wrong with the AI service. Please try again."

    def ask_with_image(self, prompt: str, image_path: str) -> str:
        """
        Send an image + prompt to Google Gemini and return the reply.
        """
        if not self.api_key or self.api_key.startswith("YOUR_"):
            return (
                "For screen analysis, please add your Gemini API key to .env. "
                "You can get one for free at Google AI Studio."
            )

        try:
            import base64
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
            
            # Construct multimodal payload
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": base64_image
                                }
                            }
                        ]
                    }
                ],
                "systemInstruction": {
                    "parts": [{"text": SYSTEM_PROMPT}]
                },
                "generationConfig": {
                    "maxOutputTokens": 300,
                    "temperature": 0.4
                }
            }
            
            resp = requests.post(
                url,
                headers={"content-type": "application/json"},
                json=payload,
                timeout=25,
            )
            resp.raise_for_status()
            
            resp_data = resp.json()
            reply = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            # We don't store large image objects in conversation text history,
            # but we can store the text response to keep context.
            self._history.append({"role": "user", "content": "[Screenshot Captured]"})
            self._history.append({"role": "assistant", "content": reply})
            
            return reply

        except requests.exceptions.ConnectionError:
            return "I can't reach the internet right now. Please check your connection."
        except requests.exceptions.HTTPError as exc:
            logger.exception("Gemini API error during image analysis")
            return f"AI service error ({exc.response.status_code}). Please try again."
        except Exception as exc:
            logger.exception("Chat API unexpected error during image analysis")
            return "Something went wrong with the AI service during image analysis. Please try again."

    def clear_history(self):
        self._history.clear()
