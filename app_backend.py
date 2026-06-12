"""
app_backend.py — Flask backend for the Premium Web Dashboard Voice Assistant.
Exposes APIs for AI chat, weather, news, reminders, system diagnostics, and screenshot vision.
"""
import logging
import os
import re
import subprocess
import threading
import datetime
from flask import Flask, jsonify, request, render_template

from core.assistant import Assistant

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")
assistant = Assistant()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.json or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Empty message"}), 400

    display, spoken = assistant.handle(text)
    return jsonify({
        "display": display,
        "spoken": spoken
    })


@app.route("/api/weather", methods=["GET"])
def api_weather():
    city = request.args.get("city", "").strip()
    if not city:
        from config import DEFAULT_CITY
        city = DEFAULT_CITY

    data = assistant.weather.get_current(city)
    return jsonify(data)


@app.route("/api/news", methods=["GET"])
def api_news():
    cat = request.args.get("category", "general").strip()
    data = assistant.news.get_headlines(cat)
    return jsonify(data)


@app.route("/api/reminders", methods=["GET", "POST", "DELETE"])
def api_reminders():
    if request.method == "GET":
        rems = assistant.reminders.all()
        # Map objects to serializable dicts
        return jsonify([
            {
                "id": r.id,
                "message": r.message,
                "time_str": r.time_str,
                "fired": r.fired
            }
            for r in rems
        ])

    elif request.method == "POST":
        data = request.json or {}
        msg = data.get("message", "").strip()
        time_str = data.get("time_str", "").strip() or None
        if not msg:
            return jsonify({"error": "Message is required"}), 400
        
        r = assistant.reminders.add(message=msg, time_str=time_str)
        return jsonify({
            "id": r.id,
            "message": r.message,
            "time_str": r.time_str,
            "fired": r.fired
        })

    elif request.method == "DELETE":
        rid = request.args.get("id", "").strip()
        if not rid:
            return jsonify({"error": "ID is required"}), 400
        assistant.reminders.delete(rid)
        return jsonify({"status": "deleted"})


@app.route("/api/stats", methods=["GET"])
def api_stats():
    try:
        import psutil
        
        # CPU
        cpu = psutil.cpu_percent()
        
        # RAM
        ram = psutil.virtual_memory()
        ram_pct = ram.percent
        ram_gb = f"{ram.used / (1024**3):.1f}/{ram.total / (1024**3):.1f} GB"
        
        # Disk
        disk = psutil.disk_usage("/")
        disk_pct = disk.percent
        disk_gb = f"{disk.used / (1024**3):.1f}/{disk.total / (1024**3):.1f} GB"
        
        # Battery level (macOS pmset tool)
        battery_info = "N/A"
        try:
            out = subprocess.check_output(["pmset", "-g", "batt"]).decode()
            m = re.search(r"(\d+)%", out)
            if m:
                pct = m.group(1)
                # Correct battery logic: check discharging first
                if "discharging" in out:
                    state = "discharging"
                elif "charging" in out:
                    state = "charging"
                elif "charged" in out:
                    state = "fully charged"
                else:
                    state = "unknown"
                battery_info = f"{pct}% ({state})"
        except Exception:
            pass
            
        return jsonify({
            "cpu": cpu,
            "ram": ram_pct,
            "ram_gb": ram_gb,
            "disk": disk_pct,
            "disk_gb": disk_gb,
            "battery": battery_info,
            "threads": threading.active_count(),
            "time": datetime.datetime.now().strftime("%I:%M:%S %p")
        })
    except Exception as e:
        logger.error("Failed to gather stats: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/screenshot", methods=["POST"])
def api_screenshot():
    try:
        from PIL import ImageGrab
        import base64
        import io
        
        # Capture desktop with macOS permission checks
        try:
            screenshot = ImageGrab.grab()
        except Exception as grab_exc:
            logger.warning("Failed to grab screen: %s", grab_exc)
            return jsonify({
                "error": (
                    "Screen Recording permission is required on macOS. "
                    "Please go to System Settings > Privacy & Security > "
                    "Screen & System Audio Recording and allow access for your Terminal or IDE."
                )
            })
        
        # Save to memory stream to encode to base64
        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG")
        img_bytes = buffer.getvalue()
        base64_image = base64.b64encode(img_bytes).decode("utf-8")
        
        # Save locally as reference/debug
        screenshot.save("screenshot_last.png")
        
        # Ask Gemini to describe the image
        prompt = (
            "You are looking at a screenshot of the user's screen. "
            "Describe what is visible concisely in 2-3 sentences. "
            "Identify the active windows, websites, or applications, and summarize the main content."
        )
        description = assistant.chat.ask_with_image(prompt, "screenshot_last.png")
        
        # Remove local file
        if os.path.exists("screenshot_last.png"):
            os.remove("screenshot_last.png")
            
        data_url = f"data:image/png;base64,{base64_image}"
        
        return jsonify({
            "description": description,
            "image": data_url
        })
    except Exception as e:
        logger.exception("Screenshot vision request failed")
        return jsonify({"error": str(e)}), 500
