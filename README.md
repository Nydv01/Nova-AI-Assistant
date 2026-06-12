# 🎤 Voice Assistant

A clean, full-featured personal voice assistant built in Python with a Tkinter desktop UI.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                  UI Layer                   │
│  ui/app_window.py  — Tkinter desktop GUI    │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│               Core Layer                    │
│  core/assistant.py    — Orchestrator        │
│  core/intent_router.py — NLP / routing      │
│  core/voice_engine.py — STT + TTS           │
└──────┬──────────────────────────┬───────────┘
       │                          │
┌──────▼──────┐          ┌────────▼──────────┐
│  API Layer  │          │  Storage Layer    │
│  weather_api│          │  reminder_store   │
│  news_api   │          │  (reminders.json) │
│  ai_chat    │          └───────────────────┘
└─────────────┘
```

### Design decisions

| Choice | Reason |
|---|---|
| **Python + Tkinter** | Zero extra GUI dependency; ships with Python; runs on macOS/Windows/Linux |
| **SpeechRecognition** | Simple wrapper around Google Web Speech API; free, accurate |
| **pyttsx3** | Offline TTS — works without internet or API key |
| **Requests** | Lightweight, no async complexity needed for a desktop app |
| **Flat JSON storage** | Simple, human-readable, no DB setup required |
| **Rule-based intent routing** | Reliable, fast, explainable; AI chat handles everything else |

---

## Folder structure

```
voice_assistant/
├── main.py                   Entry point
├── config.py                 API keys & app defaults
├── requirements.txt          Python dependencies
├── .env.example              API key template
├── reminders.json            Created automatically at runtime
│
├── core/
│   ├── assistant.py          Orchestrates all intent handlers
│   ├── intent_router.py      Maps text → intent + entities
│   └── voice_engine.py       Speech recognition & TTS
│
├── api/
│   ├── weather_api.py        OpenWeatherMap client
│   ├── news_api.py           NewsAPI client
│   └── ai_chat.py            Anthropic Claude client
│
├── storage/
│   └── reminder_store.py     Persistent reminders + scheduler
│
└── ui/
    └── app_window.py         Tkinter GUI
```

---

## Setup & installation

### Prerequisites
- Python 3.11 or higher
- pip

### 1. Clone / download the project

```bash
cd voice_assistant
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install system audio dependency

**macOS**
```bash
brew install portaudio
```

**Ubuntu / Debian**
```bash
sudo apt-get install portaudio19-dev python3-tk
```

**Windows** — no extra step needed; PyAudio provides a pre-built wheel.

### 4. Install Python packages

```bash
pip install -r requirements.txt
```

### 5. Configure API keys

Copy the template and add your keys:

```bash
cp .env.example .env
```

Then open `.env` and fill in your keys:

```
WEATHER_API_KEY=abc123...     # https://openweathermap.org/api
NEWS_API_KEY=def456...         # https://newsapi.org
ANTHROPIC_API_KEY=sk-ant-...  # https://console.anthropic.com
```

> **The app works without API keys** — weather and news will return demo data,
> and general chat will prompt you to add the Anthropic key.

---

## Running the app

```bash
python main.py
```

---

## Usage examples

| Voice command | What happens |
|---|---|
| "What's the weather in Tokyo?" | Fetches live weather and reads it aloud |
| "Read me tech headlines" | Fetches top technology news |
| "Remind me to take my medication at 8pm" | Sets a reminder; fires notification at 8:00 PM |
| "What time is it?" | Speaks the current time |
| "Tell me a joke" | Responds with a random joke |
| "Hello" | Greeting response |
| "What can you do?" | Lists available commands |
| Any other question | Routes to AI chat (requires Anthropic key) |

---

## API key guide

| Key | Where to get | Free tier |
|---|---|---|
| `WEATHER_API_KEY` | [openweathermap.org/api](https://openweathermap.org/api) | 60 calls/min, forever free |
| `NEWS_API_KEY` | [newsapi.org](https://newsapi.org) | 100 requests/day |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Pay-per-use (~$0.003/reply) |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `No module named 'pyaudio'` | See PyAudio install notes in requirements.txt |
| `No module named 'tkinter'` | `sudo apt install python3-tk` (Linux) |
| Microphone not detected | Check system permissions; try a different input device |
| Speech not recognised | Speak clearly; ensure stable internet (Google Speech API) |
| TTS has no audio | Check system volume and default audio output device |
| Weather/news returns demo data | Add API keys to `.env` file |

---

## Future improvements

- **Continuous listening** — wake-word detection ("Hey Assistant") so you never press the mic button
- **Multi-language support** — locale-aware STT and TTS voices
- **Smart home integration** — IFTTT or Home Assistant webhooks for lights, locks, etc.
- **Calendar sync** — Google Calendar / iCal integration for reminders
- **Offline AI** — swap Anthropic API for a local model via Ollama
- **Voice profiles** — per-user settings saved locally
- **Plugin architecture** — drop-in new capabilities without modifying core code
- **Web version** — Flask + WebSocket backend with the included browser app
