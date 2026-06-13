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
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
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
            logger.warning("Gemini ConnectionError - falling back to rule-based chat")
            return self.get_fallback_response(text)
        except requests.exceptions.HTTPError as exc:
            logger.warning("Gemini HTTPError (%s) - falling back to rule-based chat", exc.response.status_code)
            return self.get_fallback_response(text)
        except Exception as exc:
            logger.exception("Chat API unexpected error - falling back to rule-based chat")
            return self.get_fallback_response(text)

    def get_fallback_response(self, text: str) -> str:
        """
        Produces natural conversational responses when the Gemini API is offline
        or rate-limited (e.g. 503 error), making the bot feel organic.
        """
        lower = text.lower().strip()
        
        # Greetings
        if any(w in lower for w in ["hi", "hello", "hey", "greetings", "good morning", "good afternoon"]):
            return "Hi there! Nova here. How can I help you today?"
            
        # How are you
        if "how are you" in lower or "how's it going" in lower or "how do you do" in lower:
            return "I'm doing great, thank you! I hope you're having a wonderful day."
            
        # Identity
        if "your name" in lower or "who are you" in lower or "what are you" in lower:
            return "I am Nova, your personal AI Assistant, featuring real-time diagnostics, screen vision, and dynamic tools."
            
        # Thanks
        if any(w in lower for w in ["thank you", "thanks", "awesome", "perfect", "great"]):
            return "You're very welcome! Let me know if you need help with weather, news, screenshots, or reminders."
            
        # Capabilities / Help
        if "what can you do" in lower or "help" in lower or "capabilities" in lower:
            return "I can take screenshots and explain them, display live system diagnostics (CPU/RAM), set reminders, check weather, and read news!"
            
        # Default fallback explanation
        return (
            "I'd love to discuss that! However, my AI cognitive service is temporarily "
            "experiencing a rate limit (Error 503). In the meantime, feel free to try my other features "
            "like taking a screenshot, checking system diagnostics, or adding a reminder!"
        )

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

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
            
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
            return "I cannot analyze your screen right now because I am offline. Please check your internet connection."
        except requests.exceptions.HTTPError as exc:
            logger.exception("Gemini API error during image analysis")
            if exc.response.status_code == 503:
                return "My vision service is temporarily congested (Error 503). Please wait a few seconds and try capturing again!"
            return f"My vision service encountered an error ({exc.response.status_code}). Please try again."
        except Exception as exc:
            logger.exception("Chat API unexpected error during image analysis")
            return "Something went wrong with the vision service. Please try again."

    def clear_history(self):
        self._history.clear()
