"""
Voice Assistant — Main Entry Point
Run with: python main.py
"""
import sys
import os
import webbrowser
import threading

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(__file__))

from app_backend import app


def main():
    # Open browser automatically after 1.5 seconds to let Flask start
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
