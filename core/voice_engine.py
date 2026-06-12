"""
core/voice_engine.py — Speech recognition and text-to-speech.

Uses:
  - SpeechRecognition (speech-to-text via Google Web Speech API)
  - pyttsx3 (offline text-to-speech)
"""
import threading
import queue
import logging

import speech_recognition as sr
import pyttsx3

from config import SPEECH_RATE, SPEECH_VOLUME

logger = logging.getLogger(__name__)


class VoiceEngine:
    """
    Manages both speech recognition (STT) and text-to-speech (TTS).
    All TTS work runs in a dedicated background thread to keep the UI responsive.
    """

    def __init__(self):
        # --- Speech recognition ---
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 0.8   # seconds of silence before end-of-phrase
        self.recognizer.dynamic_energy_threshold = True

        # --- TTS engine ---
        self._tts_engine = pyttsx3.init()
        self._apply_tts_settings(SPEECH_RATE, SPEECH_VOLUME)

        # TTS runs in its own thread so it never blocks the UI
        self._tts_queue: queue.Queue = queue.Queue()
        self._tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self._tts_thread.start()

        self.enabled = True        # can be toggled from settings
        self.tts_enabled = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_rate(self, wpm: int):
        self._tts_engine.setProperty("rate", wpm)

    def set_volume(self, volume: float):
        self._tts_engine.setProperty("volume", max(0.0, min(1.0, volume)))

    def speak(self, text: str):
        """Queue text for speech output (non-blocking)."""
        if not self.tts_enabled:
            return
        # Strip any leftover markdown or HTML
        clean = self._strip_markup(text)
        self._tts_queue.put(clean)

    def listen_once(self, timeout: int = 5, phrase_limit: int = 10) -> str | None:
        """
        Capture one utterance from the microphone and return recognised text,
        or None on failure. Blocking – call from a worker thread.
        """
        if not self.enabled:
            return None
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
            return self.recognizer.recognize_google(audio)
        except sr.WaitTimeoutError:
            logger.debug("Microphone timeout – no speech detected.")
        except sr.UnknownValueError:
            logger.debug("Could not understand audio.")
        except sr.RequestError as exc:
            logger.warning("Speech recognition service error: %s", exc)
        except OSError as exc:
            logger.error("Microphone access error: %s", exc)
        return None

    def stop_speaking(self):
        """Interrupt current speech."""
        try:
            self._tts_engine.stop()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_tts_settings(self, rate: int, volume: float):
        self._tts_engine.setProperty("rate", rate)
        self._tts_engine.setProperty("volume", volume)

    def _tts_worker(self):
        """Runs in background; consumes the TTS queue serially."""
        while True:
            text = self._tts_queue.get()
            try:
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
            except Exception as exc:
                logger.warning("TTS error: %s", exc)
            finally:
                self._tts_queue.task_done()

    @staticmethod
    def _strip_markup(text: str) -> str:
        import re
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"[🌤📰⏰💬🎤☀️🌧🌩]", "", text)
        return text.strip()
