"""
ui/app_window.py — Main Tkinter desktop UI.

Layout:
  Left sidebar  : navigation tabs (Chat, Reminders, News, Dashboard, Settings)
  Right content : swappable panels per tab
  Bottom bar    : mic button + text input + send button + waveform visualizer
"""
import threading
import tkinter as tk
from tkinter import ttk, font as tkfont
import datetime
import logging
import math
import os
import re

from core.voice_engine import VoiceEngine
from core.assistant import Assistant

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Palette — Premium Dark Theme (Indigo/Violet Accents)
# --------------------------------------------------------------------------
COLORS = {
    "bg":           "#0D0E15",       # Deep slate-black
    "sidebar":      "#161722",      # Deep navy-slate
    "card":         "#1E1F2F",         # Card background
    "card_border":  "#2A2C3F",  # Card border/separator
    "accent":       "#6366F1",       # Indigo (modern neon accent)
    "accent_light": "#252841", # Soft highlight (active tab bg)
    "accent_text":  "#818CF8",  # Highlighted text color
    "text_primary": "#F3F4F6", # Main text color
    "text_secondary":"#9CA3AF",# Subtext/secondary labels
    "text_muted":   "#4B5563",   # Muted/disabled text
    "user_bubble":  "#6366F1",  # User message bubble (purple-indigo)
    "user_text":    "#FFFFFF",
    "asst_bubble":  "#1E1F2F",  # Assistant message bubble
    "status_ready": "#10B981", # Active/Ready green
    "status_listen":"#EF4444",# Listening red
    "status_proc":  "#F59E0B",  # Processing orange
    "danger":       "#EF4444",       # Red
}


# --------------------------------------------------------------------------
# Custom FlatButton (Bypasses macOS Tkinter button limitations)
# --------------------------------------------------------------------------
class FlatButton(tk.Label):
    def __init__(self, parent, text, command, bg, fg, activebackground=None, activeforeground=None, font=None, anchor="center", cursor="hand2", padx=10, pady=5, **kwargs):
        self.command = command
        self.normal_bg = bg
        self.normal_fg = fg
        self.active_bg = activebackground or bg
        self.active_fg = activeforeground or fg
        
        super().__init__(
            parent, text=text, bg=bg, fg=fg, font=font, 
            anchor=anchor, cursor=cursor, padx=padx, pady=pady, **kwargs
        )
        
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        
    def _on_enter(self, event):
        super().configure(bg=self.active_bg, fg=self.active_fg)
        
    def _on_leave(self, event):
        super().configure(bg=self.normal_bg, fg=self.normal_fg)
        
    def configure(self, **kwargs):
        if "bg" in kwargs:
            self.normal_bg = kwargs["bg"]
        if "fg" in kwargs:
            self.normal_fg = kwargs["fg"]
        if "activebackground" in kwargs:
            self.active_bg = kwargs["activebackground"]
        if "activeforeground" in kwargs:
            self.active_fg = kwargs["activeforeground"]
        super().configure(**kwargs)


class VoiceAssistantApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Premium Voice Assistant")
        self.root.geometry("920x680")
        self.root.minsize(780, 580)
        self.root.configure(bg=COLORS["bg"])

        # Configure dark-mode scrollbars and basic theme
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "TScrollbar",
            background=COLORS["card"],
            troughcolor=COLORS["bg"],
            bordercolor=COLORS["card_border"],
            arrowcolor=COLORS["text_secondary"]
        )

        self.voice = VoiceEngine()
        self.assistant = Assistant(on_reminder_fire=self._on_reminder_fire)

        self._active_panel = "chat"
        self._is_listening = False
        self._current_state = "ready"
        self._wave_phase = 0.0

        self._build_ui()
        self._add_welcome_message()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self):
        self.root.mainloop()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Sidebar
        self._build_sidebar()

        # Main content area
        content = tk.Frame(self.root, bg=COLORS["bg"])
        content.grid(row=0, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        self._build_topbar(content)
        self._build_panels(content)
        self._build_input_bar(content)

    def _build_sidebar(self):
        sidebar = tk.Frame(self.root, bg=COLORS["sidebar"], width=220,
                           highlightthickness=1, highlightbackground=COLORS["card_border"])
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.pack_propagate(False)

        # Logo
        logo_frame = tk.Frame(sidebar, bg=COLORS["sidebar"])
        logo_frame.pack(fill="x", padx=16, pady=(20, 8))
        logo_box = tk.Label(logo_frame, text="🎤", bg=COLORS["accent"],
                            fg=COLORS["user_text"], font=("", 14), width=2,
                            padx=6, pady=4)
        logo_box.pack(side="left")
        tk.Label(logo_frame, text="Assistant", bg=COLORS["sidebar"],
                 fg=COLORS["text_primary"], font=("", 12, "bold")).pack(side="left", padx=8)

        # Nav section label
        tk.Label(sidebar, text="NAVIGATION", bg=COLORS["sidebar"],
                 fg=COLORS["text_muted"], font=("", 9, "bold")).pack(anchor="w", padx=16, pady=(16, 4))

        # Nav buttons (using custom FlatButton)
        nav_items = [
            ("chat",      "💬  Chat"),
            ("reminders", "⏰  Reminders"),
            ("news",      "📰  News"),
            ("dashboard", "📊  System Stats"),
            ("settings",  "⚙️  Settings"),
        ]
        self._nav_btns = {}
        for key, label in nav_items:
            btn = FlatButton(
                sidebar, text=label, anchor="w", padx=16, pady=8,
                bg=COLORS["sidebar"], fg=COLORS["text_secondary"],
                activebackground=COLORS["accent_light"],
                activeforeground=COLORS["accent_text"],
                font=("", 11),
                command=lambda k=key: self._switch_panel(k),
            )
            btn.pack(fill="x", padx=8, pady=2)
            self._nav_btns[key] = btn

        self._nav_btns["chat"].configure(
            bg=COLORS["accent_light"], fg=COLORS["accent_text"], font=("", 11, "bold")
        )

    def _build_topbar(self, parent):
        bar = tk.Frame(parent, bg=COLORS["card"],
                       highlightthickness=1, highlightbackground=COLORS["card_border"])
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)

        self._title_label = tk.Label(bar, text="Chat", bg=COLORS["card"],
                                     fg=COLORS["text_primary"], font=("", 12, "bold"))
        self._title_label.grid(row=0, column=0, padx=16, pady=12, sticky="w")

        self._status_frame = tk.Frame(bar, bg=COLORS["accent_light"],
                                      highlightthickness=1,
                                      highlightbackground=COLORS["card_border"])
        self._status_frame.grid(row=0, column=2, padx=16, pady=8, sticky="e")
        self._status_dot = tk.Label(self._status_frame, text="●", bg=COLORS["accent_light"],
                                    fg=COLORS["status_ready"], font=("", 9))
        self._status_dot.pack(side="left", padx=(6, 2), pady=4)
        self._status_text = tk.Label(self._status_frame, text="Ready",
                                     bg=COLORS["accent_light"], fg=COLORS["text_secondary"],
                                     font=("", 10))
        self._status_text.pack(side="left", padx=(0, 8), pady=4)

    def _build_panels(self, parent):
        container = tk.Frame(parent, bg=COLORS["bg"])
        container.grid(row=1, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self._panels = {}

        for name in ("chat", "reminders", "news", "dashboard", "settings"):
            frame = tk.Frame(container, bg=COLORS["bg"])
            frame.grid(row=0, column=0, sticky="nsew")
            self._panels[name] = frame

        self._build_chat_panel(self._panels["chat"])
        self._build_reminders_panel(self._panels["reminders"])
        self._build_news_panel(self._panels["news"])
        self._build_dashboard_panel(self._panels["dashboard"])
        self._build_settings_panel(self._panels["settings"])

        self._panels["chat"].lift()

    # ---- Chat panel ----
    def _build_chat_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        frame = tk.Frame(parent, bg=COLORS["bg"])
        frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        # Scrollable message area
        self._chat_canvas = tk.Canvas(frame, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self._chat_canvas.yview)
        self._chat_canvas.configure(yscrollcommand=scrollbar.set)
        self._chat_canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self._msg_frame = tk.Frame(self._chat_canvas, bg=COLORS["bg"])
        self._msg_window = self._chat_canvas.create_window(
            (0, 0), window=self._msg_frame, anchor="nw"
        )
        self._msg_frame.bind("<Configure>", self._on_msg_frame_configure)
        self._chat_canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_msg_frame_configure(self, event):
        self._chat_canvas.configure(scrollregion=self._chat_canvas.bbox("all"))
        self._chat_canvas.yview_moveto(1.0)

    def _on_canvas_configure(self, event):
        self._chat_canvas.itemconfig(self._msg_window, width=event.width)

    # ---- Reminders panel ----
    def _build_reminders_panel(self, parent):
        parent.columnconfigure(0, weight=1)

        # Form card
        card = self._make_card(parent)
        card.pack(fill="x", padx=16, pady=(16, 8))

        tk.Label(card, text="New Reminder", bg=COLORS["card"],
                 fg=COLORS["text_primary"], font=("", 10, "bold")).pack(anchor="w", pady=(0, 8))

        self._rem_msg_var = tk.StringVar()
        tk.Label(card, text="Message", bg=COLORS["card"], fg=COLORS["text_secondary"],
                 font=("", 9)).pack(anchor="w")
        tk.Entry(card, textvariable=self._rem_msg_var, font=("", 11),
                 relief="flat", bg=COLORS["bg"],
                 fg=COLORS["text_primary"],
                 highlightthickness=1, highlightbackground=COLORS["card_border"],
                 highlightcolor=COLORS["accent"]).pack(fill="x", pady=(2, 8), ipady=6)

        row = tk.Frame(card, bg=COLORS["card"])
        row.pack(fill="x")

        self._rem_time_var = tk.StringVar()
        tframe = tk.Frame(row, bg=COLORS["card"])
        tframe.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Label(tframe, text="Time (HH:MM)", bg=COLORS["card"],
                 fg=COLORS["text_secondary"], font=("", 9)).pack(anchor="w")
        tk.Entry(tframe, textvariable=self._rem_time_var, font=("", 11),
                 relief="flat", bg=COLORS["bg"],
                 fg=COLORS["text_primary"], width=10,
                 highlightthickness=1, highlightbackground=COLORS["card_border"],
                 highlightcolor=COLORS["accent"]).pack(fill="x", pady=(2, 0), ipady=6)

        btn = FlatButton(
            row, text="＋ Add", bg=COLORS["accent"], fg=COLORS["user_text"],
            activebackground=COLORS["accent_text"], activeforeground=COLORS["user_text"],
            font=("", 10, "bold"), padx=18, pady=8,
            command=self._gui_add_reminder
        )
        btn.pack(side="right", anchor="s")

        # Reminder list
        list_frame = tk.Frame(parent, bg=COLORS["bg"])
        list_frame.pack(fill="both", expand=True, padx=16, pady=4)
        list_frame.columnconfigure(0, weight=1)

        canvas = tk.Canvas(list_frame, bg=COLORS["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        list_frame.rowconfigure(0, weight=1)

        self._rem_inner = tk.Frame(canvas, bg=COLORS["bg"])
        win = canvas.create_window((0, 0), window=self._rem_inner, anchor="nw")
        self._rem_inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        self._rem_canvas = canvas

        self._refresh_reminder_list()

    # ---- News panel ----
    def _build_news_panel(self, parent):
        parent.columnconfigure(0, weight=1)

        # Category buttons
        cat_frame = tk.Frame(parent, bg=COLORS["bg"])
        cat_frame.pack(fill="x", padx=16, pady=(16, 8))
        self._news_cat = tk.StringVar(value="general")

        from config import NEWS_CATEGORIES
        for cat in NEWS_CATEGORIES[:5]:
            tk.Radiobutton(
                cat_frame, text=cat.capitalize(), variable=self._news_cat,
                value=cat, bg=COLORS["bg"], fg=COLORS["text_secondary"],
                selectcolor=COLORS["sidebar"], activebackground=COLORS["bg"],
                font=("", 10), relief="flat", cursor="hand2",
                command=self._load_news,
            ).pack(side="left", padx=6)

        # News list
        inner = tk.Frame(parent, bg=COLORS["bg"])
        inner.pack(fill="both", expand=True, padx=16, pady=4)
        inner.columnconfigure(0, weight=1)
        inner.rowconfigure(0, weight=1)

        canvas = tk.Canvas(inner, bg=COLORS["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(inner, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        inner.rowconfigure(0, weight=1)

        self._news_inner = tk.Frame(canvas, bg=COLORS["bg"])
        win = canvas.create_window((0, 0), window=self._news_inner, anchor="nw")
        self._news_inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))

        self._load_news()

    # ---- System Stats Dashboard panel ----
    def _build_dashboard_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        
        scroll_frame = tk.Frame(parent, bg=COLORS["bg"])
        scroll_frame.pack(fill="both", expand=True, padx=16, pady=16)
        
        # CPU Card
        cpu_card = self._make_card(scroll_frame)
        cpu_card.pack(fill="x", pady=(0, 12))
        tk.Label(cpu_card, text="CPU Diagnostics", bg=COLORS["card"], fg=COLORS["text_primary"],
                 font=("", 11, "bold")).pack(anchor="w", pady=(0, 8))
                 
        self._cpu_val_lbl = tk.Label(cpu_card, text="CPU Load: Checking...", bg=COLORS["card"],
                                     fg=COLORS["accent_text"], font=("", 10))
        self._cpu_val_lbl.pack(anchor="w")
        
        self._cpu_progress = tk.Canvas(cpu_card, bg=COLORS["card_border"], height=8, highlightthickness=0)
        self._cpu_progress.pack(fill="x", pady=(6, 0))
        self._cpu_bar = self._cpu_progress.create_rectangle(0, 0, 0, 8, fill=COLORS["accent"], outline="")
        
        # RAM Card
        ram_card = self._make_card(scroll_frame)
        ram_card.pack(fill="x", pady=(0, 12))
        tk.Label(ram_card, text="Memory Diagnostics", bg=COLORS["card"], fg=COLORS["text_primary"],
                 font=("", 11, "bold")).pack(anchor="w", pady=(0, 8))
                 
        self._ram_val_lbl = tk.Label(ram_card, text="RAM Used: Checking...", bg=COLORS["card"],
                                     fg=COLORS["accent_text"], font=("", 10))
        self._ram_val_lbl.pack(anchor="w")
        
        self._ram_progress = tk.Canvas(ram_card, bg=COLORS["card_border"], height=8, highlightthickness=0)
        self._ram_progress.pack(fill="x", pady=(6, 0))
        self._ram_bar = self._ram_progress.create_rectangle(0, 0, 0, 8, fill=COLORS["accent"], outline="")
        
        # General Storage & System Card
        sys_card = self._make_card(scroll_frame)
        sys_card.pack(fill="x", pady=(0, 12))
        tk.Label(sys_card, text="System & Battery Metrics", bg=COLORS["card"], fg=COLORS["text_primary"],
                 font=("", 11, "bold")).pack(anchor="w", pady=(0, 8))
                 
        self._sys_info_lbl = tk.Label(sys_card, text="Loading system metrics...", bg=COLORS["card"],
                                      fg=COLORS["text_secondary"], font=("", 10), justify="left", anchor="w")
        self._sys_info_lbl.pack(fill="x")
        
        # Start the update loop
        self._update_dashboard_loop()

    def _update_dashboard_loop(self):
        if self._active_panel == "dashboard":
            try:
                import psutil
                import subprocess
                
                # Update CPU
                cpu = psutil.cpu_percent()
                self._cpu_val_lbl.configure(text=f"CPU Load: {cpu}%")
                w_cpu = self._cpu_progress.winfo_width()
                if w_cpu > 10:
                    self._cpu_progress.coords(self._cpu_bar, 0, 0, int(w_cpu * (cpu / 100)), 8)
                
                # Update RAM
                ram = psutil.virtual_memory()
                ram_pct = ram.percent
                ram_gb = f"{ram.used / (1024**3):.1f}/{ram.total / (1024**3):.1f} GB"
                self._ram_val_lbl.configure(text=f"RAM Used: {ram_pct}% ({ram_gb})")
                w_ram = self._ram_progress.winfo_width()
                if w_ram > 10:
                    self._ram_progress.coords(self._ram_bar, 0, 0, int(w_ram * (ram_pct / 100)), 8)
                
                # Update Disk & System metrics
                disk = psutil.disk_usage("/")
                disk_pct = disk.percent
                disk_gb = f"{disk.used / (1024**3):.1f}/{disk.total / (1024**3):.1f} GB"
                
                battery = "N/A"
                try:
                    out = subprocess.check_output(["pmset", "-g", "batt"]).decode()
                    m = re.search(r"(\d+)%", out)
                    if m:
                        battery = f"{m.group(1)}% ({'charging' if 'charging' in out else 'discharging'})"
                except Exception:
                    pass
                    
                info = (
                    f"🔋 Battery level  : {battery}\n"
                    f"💾 Disk space (/): {disk_pct}% ({disk_gb})\n"
                    f"🚀 Active threads : {threading.active_count()}\n"
                    f"⏰ Local time     : {datetime.datetime.now().strftime('%I:%M:%S %p')}"
                )
                self._sys_info_lbl.configure(text=info)
            except Exception as e:
                logger.error("Dashboard update failed: %s", e)
                
        # Fire again in 1 second
        self.root.after(1000, self._update_dashboard_loop)

    # ---- Settings panel ----
    def _build_settings_panel(self, parent):
        parent.columnconfigure(0, weight=1)

        scroll_frame = tk.Frame(parent, bg=COLORS["bg"])
        scroll_frame.pack(fill="both", expand=True, padx=16, pady=16)

        card = self._make_card(scroll_frame)
        card.pack(fill="x", pady=(0, 12))
        tk.Label(card, text="Voice", bg=COLORS["card"], fg=COLORS["text_primary"],
                 font=("", 10, "bold")).grid(row=0, column=0, sticky="w", columnspan=2, pady=(0, 8))

        # Speech recognition toggle
        self._sr_var = tk.BooleanVar(value=True)
        self._make_toggle_row(card, 1, "Speech recognition", self._sr_var,
                              lambda: setattr(self.voice, "enabled", self._sr_var.get()))

        # TTS toggle
        self._tts_var = tk.BooleanVar(value=True)
        self._make_toggle_row(card, 2, "Auto-speak replies", self._tts_var,
                              lambda: setattr(self.voice, "tts_enabled", self._tts_var.get()))

        # Speed slider
        tk.Label(card, text="Voice speed", bg=COLORS["card"],
                 fg=COLORS["text_secondary"], font=("", 10)).grid(row=3, column=0, sticky="w", pady=(8, 0))
        speed_var = tk.DoubleVar(value=175)
        tk.Scale(card, from_=80, to=260, orient="horizontal", variable=speed_var,
                 bg=COLORS["card"], fg=COLORS["text_primary"], highlightthickness=0,
                 troughcolor=COLORS["bg"], activebackground=COLORS["accent"],
                 command=lambda v: self.voice.set_rate(int(float(v)))).grid(
            row=3, column=1, sticky="ew", padx=(8, 0))
        card.columnconfigure(1, weight=1)

        # Volume slider
        tk.Label(card, text="Volume", bg=COLORS["card"],
                 fg=COLORS["text_secondary"], font=("", 10)).grid(row=4, column=0, sticky="w", pady=(4, 0))
        vol_var = tk.DoubleVar(value=0.9)
        tk.Scale(card, from_=0, to=1, resolution=0.05, orient="horizontal", variable=vol_var,
                 bg=COLORS["card"], fg=COLORS["text_primary"], highlightthickness=0,
                 troughcolor=COLORS["bg"], activebackground=COLORS["accent"],
                 command=lambda v: self.voice.set_volume(float(v))).grid(
            row=4, column=1, sticky="ew", padx=(8, 0))

        # API keys
        key_card = self._make_card(scroll_frame)
        key_card.pack(fill="x", pady=(0, 12))
        tk.Label(key_card, text="API Keys", bg=COLORS["card"], fg=COLORS["text_primary"],
                 font=("", 10, "bold")).pack(anchor="w", pady=(0, 8))

        keys_info = [
            ("OpenWeatherMap", "WEATHER_API_KEY",  "https://openweathermap.org/api"),
            ("NewsAPI",        "NEWS_API_KEY",     "https://newsapi.org"),
            ("Google Gemini",  "GEMINI_API_KEY",   "https://aistudio.google.com/"),
        ]
        for name, var, url in keys_info:
            row = tk.Frame(key_card, bg=COLORS["card"])
            row.pack(fill="x", pady=4)
            tk.Label(row, text=name, bg=COLORS["card"], fg=COLORS["text_secondary"],
                     font=("", 10), width=16, anchor="w").pack(side="left")
            tk.Label(row, text=f"→ set {var} in .env file",
                     bg=COLORS["card"], fg=COLORS["accent_text"], font=("", 9),
                     cursor="hand2").pack(side="left")

    # ---- Input bar ----
    def _build_input_bar(self, parent):
        bar = tk.Frame(parent, bg=COLORS["card"],
                       highlightthickness=1, highlightbackground=COLORS["card_border"])
        bar.grid(row=2, column=0, sticky="ew")

        # Waveform Visualizer Canvas
        self._wave_canvas = tk.Canvas(bar, bg=COLORS["card"], height=35, highlightthickness=0)
        self._wave_canvas.pack(fill="x", padx=16, pady=(6, 0))
        self._draw_waveform() # Start animation loop!

        # Transcript area
        self._transcript_var = tk.StringVar(value="Tap the mic to speak, or type below…")
        transcript = tk.Label(bar, textvariable=self._transcript_var,
                              bg=COLORS["card"], fg=COLORS["text_secondary"],
                              font=("", 10, "italic"), anchor="w", padx=12)
        transcript.pack(fill="x", padx=12, pady=(4, 4))

        row = tk.Frame(bar, bg=COLORS["card"])
        row.pack(fill="x", padx=12, pady=(0, 10))

        # Mic button
        self._mic_btn = FlatButton(
            row, text="🎤", font=("", 14), bg=COLORS["accent_light"],
            fg=COLORS["accent"], activebackground=COLORS["accent"],
            activeforeground=COLORS["user_text"], width=2, padx=6, pady=4,
            command=self._toggle_listening,
        )
        self._mic_btn.pack(side="left", padx=(0, 8))

        # Text input
        self._text_input = tk.Entry(
            row, font=("", 11), bg=COLORS["bg"], fg=COLORS["text_primary"],
            relief="flat", insertbackground=COLORS["accent"],
            highlightthickness=1, highlightbackground=COLORS["card_border"],
            highlightcolor=COLORS["accent"]
        )
        self._text_input.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        self._text_input.bind("<Return>", lambda e: self._send_text())

        # Send button
        btn = FlatButton(
            row, text="Send →", bg=COLORS["accent"], fg=COLORS["user_text"],
            activebackground=COLORS["accent_text"], activeforeground=COLORS["user_text"],
            font=("", 10, "bold"), padx=18, pady=6,
            command=self._send_text,
        )
        btn.pack(side="right")

    # ------------------------------------------------------------------
    # Sine Waveform drawing animation loop
    # ------------------------------------------------------------------

    def _draw_waveform(self):
        if not hasattr(self, "_wave_canvas") or not self._wave_canvas:
            return
            
        canvas = self._wave_canvas
        canvas.delete("wave")
        
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10 or h < 10:
            # Re-fire until canvas size is computed
            self.root.after(40, self._draw_waveform)
            return
            
        mid_y = h / 2
        state = self._current_state  # "ready", "listening", "processing", "speaking"
        
        self._wave_phase += 0.15
        
        if state == "listening":
            # Overlapping pulsating sine waves
            waves = [
                {"color": "#818CF8", "amp": h * 0.35, "freq": 0.03, "phase_shift": 1.0},
                {"color": "#6366F1", "amp": h * 0.25, "freq": 0.045, "phase_shift": -1.5},
                {"color": "#A78BFA", "amp": h * 0.15, "freq": 0.06, "phase_shift": 0.5}
            ]
            for wave in waves:
                points = []
                for x in range(0, w + 10, 10):
                    y = mid_y + wave["amp"] * float(
                        (1.0 - abs((x - w/2) / (w/2))**2) * 
                        math.sin(x * wave["freq"] + self._wave_phase * wave["phase_shift"])
                    )
                    points.extend([x, y])
                canvas.create_line(*points, fill=wave["color"], width=2, smooth=True, tags="wave")
                
        elif state == "processing":
            # Rotating or breathing dot inside center
            center_x = w / 2
            size = 8 + 4 * math.sin(self._wave_phase * 2.0)
            canvas.create_oval(center_x - size, mid_y - size, center_x + size, mid_y + size,
                              fill=COLORS["accent"], outline=COLORS["accent_text"], width=2, tags="wave")
            for i in (-1, 1):
                px = center_x + i * 25
                psize = 4 + 2 * math.sin(self._wave_phase * 2.0 + i * 1.5)
                canvas.create_oval(px - psize, mid_y - psize, px + psize, mid_y + psize,
                                  fill=COLORS["accent_light"], outline=COLORS["accent_text"], width=1, tags="wave")
                                  
        elif state == "speaking":
            # Visualizer bars
            bar_width = 4
            gap = 6
            num_bars = int(w / (bar_width + gap)) - 2
            start_x = (w - (num_bars * (bar_width + gap))) / 2
            
            for i in range(num_bars):
                x = start_x + i * (bar_width + gap)
                height = (h * 0.4) * (0.3 + 0.7 * abs(math.sin(self._wave_phase + i * 0.3)))
                canvas.create_rectangle(x, mid_y - height, x + bar_width, mid_y + height,
                                       fill=COLORS["accent"], outline="", tags="wave")
        else:
            # Ready: clean idle line
            points = []
            for x in range(0, w + 10, 15):
                shimmer = 1.5 * math.sin(x * 0.05 + self._wave_phase * 0.5)
                points.extend([x, mid_y + shimmer])
            canvas.create_line(*points, fill=COLORS["card_border"], width=1, smooth=True, tags="wave")
            
        self.root.after(40, self._draw_waveform)

    # ------------------------------------------------------------------
    # Panel switching
    # ------------------------------------------------------------------

    def _switch_panel(self, name: str):
        self._active_panel = name
        self._panels[name].lift()
        self._title_label.configure(
            text={"chat": "Chat", "reminders": "Reminders",
                  "news": "News Headlines", "dashboard": "System Stats", "settings": "Settings"}[name]
        )
        for key, btn in self._nav_btns.items():
            if key == name:
                btn.configure(bg=COLORS["accent_light"], fg=COLORS["accent_text"],
                              font=("", 11, "bold"))
            else:
                btn.configure(bg=COLORS["sidebar"], fg=COLORS["text_secondary"],
                              font=("", 11, "normal"))

    # ------------------------------------------------------------------
    # Voice interaction
    # ------------------------------------------------------------------

    def _toggle_listening(self):
        if not self.voice.enabled:
            self._show_toast("Speech recognition is disabled in Settings.")
            return
        if self._is_listening:
            self._is_listening = False
            self._update_status("ready")
            return
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _listen_loop(self):
        self._is_listening = True
        self.root.after(0, lambda: self._mic_btn.configure(bg=COLORS["accent"],
                                                            fg=COLORS["user_text"]))
        self._update_status("listening")
        self._transcript_var.set("Listening…")

        text = self.voice.listen_once()
        self._is_listening = False
        self.root.after(0, lambda: self._mic_btn.configure(bg=COLORS["accent_light"],
                                                            fg=COLORS["accent"]))
        if text:
            self.root.after(0, lambda t=text: self._transcript_var.set(f'"{t}"'))
            self.root.after(0, lambda t=text: self._process_input(t))
        else:
            self._transcript_var.set("Didn't catch that — please try again.")
            self._update_status("ready")

    # ------------------------------------------------------------------
    # Input processing
    # ------------------------------------------------------------------

    def _send_text(self):
        text = self._text_input.get().strip()
        if not text:
            return
        self._text_input.delete(0, "end")
        self._process_input(text)

    def _process_input(self, text: str):
        self._add_user_bubble(text)
        self._update_status("processing")
        threading.Thread(target=self._get_response, args=(text,), daemon=True).start()

    def _get_response(self, text: str):
        display, spoken = self.assistant.handle(text)
        
        # Check if a screenshot was saved
        image_path = None
        if any(w in text.lower() for w in ["screenshot", "screen shot", "capture"]):
            if os.path.exists("screenshot_last.png"):
                image_path = "screenshot_last.png"
                
        self.root.after(0, lambda: self._add_bubble(display, role="assistant", image_path=image_path))
        self.root.after(0, lambda: self._update_status("ready"))
        self.voice.speak(spoken)

    # ------------------------------------------------------------------
    # Chat bubbles
    # ------------------------------------------------------------------

    def _add_user_bubble(self, text: str):
        self._add_bubble(text, role="user")

    def _add_assistant_bubble(self, text: str):
        self._add_bubble(text, role="assistant")

    def _add_welcome_message(self):
        welcome = (
            "Hello! I'm your premium voice assistant.\n\n"
            "Try: 'What's the weather in Paris?'\n"
            "      'Read me tech headlines'\n"
            "      'Take a screenshot' (and describe it!)\n"
            "      'Show my system stats'\n"
            "      'Remind me to call mom at 3pm'"
        )
        self._add_bubble(welcome, role="assistant")

    def _add_bubble(self, text: str, role: str, image_path: str = None):
        outer = tk.Frame(self._msg_frame, bg=COLORS["bg"])
        outer.pack(fill="x", padx=16, pady=5)

        is_user = role == "user"
        bubble_bg = COLORS["user_bubble"] if is_user else COLORS["asst_bubble"]
        bubble_fg = COLORS["user_text"] if is_user else COLORS["text_primary"]

        inner = tk.Frame(outer, bg=bubble_bg,
                         highlightthickness=1 if not is_user else 0,
                         highlightbackground=COLORS["card_border"])
        inner.pack(side="right" if is_user else "left", padx=4)

        # Draw screenshot if path exists
        if image_path:
            try:
                from PIL import Image, ImageTk
                img = Image.open(image_path)
                img.thumbnail((320, 200))
                photo = ImageTk.PhotoImage(img)
                img_lbl = tk.Label(inner, image=photo, bg=bubble_bg)
                img_lbl.image = photo  # Keep a reference!
                img_lbl.pack(padx=12, pady=(10, 4))
                
                # Delete screenshot file now that it is rendered in memory
                # to prevent showing old screenshots in future non-screenshot triggers
                os.remove(image_path)
            except Exception as e:
                logger.error("Failed to render image in chat bubble: %s", e)

        if text:
            lbl = tk.Label(inner, text=text, bg=bubble_bg, fg=bubble_fg,
                           font=("", 10), wraplength=480, justify="left",
                           padx=12, pady=8, anchor="w")
            lbl.pack()

        time_str = datetime.datetime.now().strftime("%I:%M %p")
        tk.Label(outer, text=time_str, bg=COLORS["bg"], fg=COLORS["text_secondary"],
                 font=("", 8)).pack(side="right" if is_user else "left", padx=6)

    # ------------------------------------------------------------------
    # Reminders UI
    # ------------------------------------------------------------------

    def _gui_add_reminder(self):
        msg = self._rem_msg_var.get().strip()
        time_str = self._rem_time_var.get().strip() or None
        if not msg:
            self._show_toast("Please enter a reminder message.")
            return
        self.assistant.reminders.add(message=msg, time_str=time_str)
        self._rem_msg_var.set("")
        self._rem_time_var.set("")
        self._refresh_reminder_list()
        self._show_toast(f"Reminder set: {msg}")

    def _refresh_reminder_list(self):
        for w in self._rem_inner.winfo_children():
            w.destroy()
        rems = self.assistant.reminders.all()
        if not rems:
            tk.Label(self._rem_inner, text="No reminders yet.",
                     bg=COLORS["bg"], fg=COLORS["text_secondary"],
                     font=("", 10, "italic")).pack(pady=20)
            return
        for r in rems:
            card = self._make_card(self._rem_inner)
            card.pack(fill="x", pady=4)
            row = tk.Frame(card, bg=COLORS["card"])
            row.pack(fill="x")
            icon = "✅" if r.fired else "⏰"
            tk.Label(row, text=icon, bg=COLORS["card"], font=("", 14), fg=COLORS["text_primary"]).pack(side="left")
            info = tk.Frame(row, bg=COLORS["card"])
            info.pack(side="left", fill="x", expand=True, padx=8)
            fg = COLORS["text_secondary"] if r.fired else COLORS["text_primary"]
            tk.Label(info, text=r.message, bg=COLORS["card"], fg=fg,
                     font=("", 10, "bold")).pack(anchor="w")
            tk.Label(info, text=r.time_str or "No time set", bg=COLORS["card"],
                     fg=COLORS["text_secondary"], font=("", 9)).pack(anchor="w")
            
            btn = FlatButton(
                row, text="✕", bg=COLORS["card"], fg=COLORS["text_muted"],
                activebackground=COLORS["danger"], activeforeground=COLORS["user_text"],
                font=("", 10), padx=8, pady=4,
                command=lambda rid=r.id: self._delete_reminder(rid)
            )
            btn.pack(side="right")

    def _delete_reminder(self, rid: str):
        self.assistant.reminders.delete(rid)
        self._refresh_reminder_list()

    def _on_reminder_fire(self, message: str):
        self.root.after(0, lambda: self._add_assistant_bubble(f"⏰ Reminder: {message}"))
        self.root.after(0, lambda: self._show_toast(f"Reminder: {message}"))
        self.root.after(0, lambda: self._refresh_reminder_list())
        self.voice.speak(f"Reminder: {message}")

    # ------------------------------------------------------------------
    # News UI
    # ------------------------------------------------------------------

    def _load_news(self):
        for w in self._news_inner.winfo_children():
            w.destroy()
        tk.Label(self._news_inner, text="Loading…", bg=COLORS["bg"],
                 fg=COLORS["text_secondary"], font=("", 10, "italic")).pack(pady=12)
        self._news_inner.update()
        cat = self._news_cat.get()
        threading.Thread(target=self._fetch_and_render_news, args=(cat,), daemon=True).start()

    def _fetch_and_render_news(self, cat: str):
        articles = self.assistant.news.get_headlines(cat)
        self.root.after(0, lambda: self._render_news(articles, cat))

    def _render_news(self, articles: list, cat: str):
        for w in self._news_inner.winfo_children():
            w.destroy()
        if not articles:
            tk.Label(self._news_inner, text="No headlines available.",
                     bg=COLORS["bg"], fg=COLORS["text_secondary"],
                     font=("", 10, "italic")).pack(pady=20)
            return
        for a in articles:
            card = self._make_card(self._news_inner)
            card.pack(fill="x", pady=4)
            tk.Label(card, text=cat.upper(), bg=COLORS["card"],
                     fg=COLORS["accent_text"], font=("", 8, "bold")).pack(anchor="w")
            tk.Label(card, text=a["title"], bg=COLORS["card"],
                     fg=COLORS["text_primary"], font=("", 10),
                     wraplength=580, justify="left").pack(anchor="w", pady=(2, 0))
            tk.Label(card, text=a["source"], bg=COLORS["card"],
                     fg=COLORS["text_secondary"], font=("", 8)).pack(anchor="w")

    # ------------------------------------------------------------------
    # Status & helpers
    # ------------------------------------------------------------------

    def _update_status(self, state: str):
        self._current_state = state
        colors = {
            "ready":      (COLORS["status_ready"],  "Ready"),
            "listening":  (COLORS["status_listen"], "Listening…"),
            "processing": (COLORS["status_proc"],   "Thinking…"),
            "speaking":   (COLORS["accent"],        "Speaking…"),
        }
        color, label = colors.get(state, (COLORS["status_ready"], "Ready"))
        self.root.after(0, lambda: self._status_dot.configure(fg=color))
        self.root.after(0, lambda: self._status_text.configure(text=label))

    def _show_toast(self, message: str):
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        x = self.root.winfo_x() + self.root.winfo_width() - 340
        y = self.root.winfo_y() + 60
        toast.geometry(f"320x50+{x}+{y}")
        tk.Label(toast, text=message, bg=COLORS["accent"], fg=COLORS["user_text"],
                 font=("", 10), padx=16, pady=12, wraplength=300).pack(fill="both", expand=True)
        toast.after(3500, toast.destroy)

    def _make_card(self, parent) -> tk.Frame:
        return tk.Frame(parent, bg=COLORS["card"],
                        highlightthickness=1, highlightbackground=COLORS["card_border"],
                        padx=14, pady=12)

    def _make_toggle_row(self, parent, row, label, var, command):
        tk.Label(parent, text=label, bg=COLORS["card"],
                 fg=COLORS["text_primary"], font=("", 10)).grid(
            row=row, column=0, sticky="w", pady=4)
        tk.Checkbutton(parent, variable=var, bg=COLORS["card"],
                       activebackground=COLORS["card"],
                       selectcolor=COLORS["card"],
                       fg=COLORS["text_primary"],
                       command=command).grid(row=row, column=1, sticky="e")
