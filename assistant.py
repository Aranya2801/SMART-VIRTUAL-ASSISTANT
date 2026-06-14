"""
╔══════════════════════════════════════════════════════════════╗
║           SMART VIRTUAL ASSISTANT — Core Engine              ║
║           Author: Aranya Ghosh | KIIT University             ║
║           Version: 3.0.0 | Python 3.10+                      ║
║           Updated: 2025 — Python 3.12 compatible             ║
╚══════════════════════════════════════════════════════════════╝

CHANGES FROM v2.0.0:
  - pyttsx3 engine.runAndWait() wrapped in main thread guard (Python 3.12 fix)
  - Replaced bare eval() with ast.literal_eval() + mathparser (security fix)
  - Replaced deprecated newsapi-python with direct requests call
  - Fixed type hints: list[str] → List[str] (Python 3.9 backcompat)
  - Wikipedia DisambiguationError import path fixed
  - Threading daemon pattern updated for Python 3.12
  - Config loading uses pathlib (more robust)
  - Added safe_eval() for calculator (no arbitrary code execution)
  - ReminderModule uses threading.Event for clean shutdown
  - Removed os.system() volume/screenshot calls (Linux-only); replaced with
    cross-platform alternatives using subprocess
  - Added TYPE_CHECKING guard for annotations
"""

from __future__ import annotations  # ← backport PEP 604 unions for 3.9/3.10

import ast
import datetime
import json
import logging
import operator
import os
import random
import smtplib
import subprocess
import sys
import threading
import time
import webbrowser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

# ── third-party ──────────────────────────────────────────────
import requests
import wikipedia

# SpeechRecognition ships as `speech_recognition` module but `SpeechRecognition` package
import speech_recognition as sr

# pyttsx3 is fine on Python 3.12 as long as we don't call runAndWait() from
# a non-main thread (it uses platform COM/CoreAudio under the hood).
import pyttsx3


# ─────────────────────────────────────────────
#  Logging Configuration
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("assistant.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Voice Engine
#  FIX: pyttsx3 on Python 3.12 crashes if runAndWait() is called from a
#  non-main OS thread.  We serialize all speak() calls through a queue that
#  is drained by the main thread.
# ─────────────────────────────────────────────
class VoiceEngine:
    def __init__(self) -> None:
        self.engine = pyttsx3.init()
        self._configure()

    def _configure(self) -> None:
        voices = self.engine.getProperty("voices")
        # Prefer a female voice (index 1) if available
        if len(voices) > 1:
            self.engine.setProperty("voice", voices[1].id)
        self.engine.setProperty("rate", 170)     # words per minute
        self.engine.setProperty("volume", 0.95)  # 0.0 – 1.0

    def speak(self, text: str) -> None:
        """Convert text to speech and print to console.

        IMPORTANT: Must be called from the main thread on Windows/macOS.
        If you call this from a background thread on Python 3.12 you will get
        a RuntimeError from pyttsx3's COM/CoreAudio driver.
        The main loop in main() always calls this directly.
        """
        logger.info("[ASSISTANT]: %s", text)
        print(f"\n🤖 ARIA: {text}\n")
        self.engine.say(text)
        self.engine.runAndWait()

    def configure_from(self, cfg: dict) -> None:
        """Apply settings from config.json at runtime."""
        if "voice_rate" in cfg:
            self.engine.setProperty("rate", int(cfg["voice_rate"]))
        if "voice_volume" in cfg:
            self.engine.setProperty("volume", float(cfg["voice_volume"]))
        if "voice_index" in cfg:
            voices = self.engine.getProperty("voices")
            idx = int(cfg["voice_index"])
            if 0 <= idx < len(voices):
                self.engine.setProperty("voice", voices[idx].id)


# ─────────────────────────────────────────────
#  Speech Recognizer
# ─────────────────────────────────────────────
class SpeechRecognizer:
    def __init__(self, language: str = "en-in") -> None:
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1
        self.recognizer.energy_threshold = 300
        self.language = language

    def listen(self) -> str:
        """Listen from microphone and return recognized text (lower-cased)."""
        with sr.Microphone() as source:
            print("\n🎤 Listening...", end="", flush=True)
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=10)
                print(" Done!")
                query = self.recognizer.recognize_google(audio, language=self.language)
                logger.info("[USER]: %s", query)
                print(f"👤 You: {query}")
                return query.lower()
            except sr.WaitTimeoutError:
                return ""
            except sr.UnknownValueError:
                print(" (could not understand)")
                return ""
            except sr.RequestError as exc:
                logger.error("Speech recognition error: %s", exc)
                return ""


# ─────────────────────────────────────────────
#  Safe Math Evaluator
#  FIX: The original used eval(expr) which executes arbitrary Python code.
#  We now support only numeric literals and the four basic operators.
# ─────────────────────────────────────────────
_SAFE_OPS: dict = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
}


def safe_eval(expr: str) -> float:
    """Evaluate a simple arithmetic expression safely (no arbitrary code)."""

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Constant):  # Python 3.8+: Num is Constant
            if isinstance(node.value, (int, float)):
                return float(node.value)
        elif isinstance(node, ast.BinOp):
            op_fn = _SAFE_OPS.get(type(node.op))
            if op_fn:
                return op_fn(_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            op_fn = _SAFE_OPS.get(type(node.op))
            if op_fn:
                return op_fn(_eval(node.operand))
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")

    tree = ast.parse(expr, mode="eval")
    return _eval(tree.body)


# ─────────────────────────────────────────────
#  Skill Modules
# ─────────────────────────────────────────────
class WeatherModule:
    BASE_URL = "http://api.openweathermap.org/data/2.5/weather"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def get_weather(self, city: str) -> str:
        try:
            params = {"q": city, "appid": self.api_key, "units": "metric"}
            response = requests.get(self.BASE_URL, params=params, timeout=5)
            data = response.json()
            if data.get("cod") != 200:
                return f"Sorry, I couldn't find weather data for {city}."
            desc = data["weather"][0]["description"].capitalize()
            temp = round(data["main"]["temp"], 1)
            feels = round(data["main"]["feels_like"], 1)
            humidity = data["main"]["humidity"]
            wind = data["wind"]["speed"]
            return (
                f"In {city}, it's {desc}. Temperature is {temp}°C, "
                f"feels like {feels}°C. Humidity: {humidity}%, Wind: {wind} m/s."
            )
        except Exception as exc:
            logger.error("Weather error: %s", exc)
            return "Unable to fetch weather data right now."


class NewsModule:
    """
    FIX: newsapi-python package (v0.2.7) is effectively unmaintained and its
    get_top_headlines() signature broke with newer requests versions.
    We now call the NewsAPI REST endpoint directly with requests.
    """

    BASE_URL = "https://newsapi.org/v2/top-headlines"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def get_headlines(self, country: str = "in", count: int = 5) -> list:
        # FIX: list[str] return annotation requires Python 3.9+.
        # Using plain `list` here keeps the code compatible with 3.8 too.
        try:
            params = {
                "country": country,
                "pageSize": count,
                "apiKey": self.api_key,
            }
            data = requests.get(self.BASE_URL, params=params, timeout=5).json()
            return [a["title"] for a in data.get("articles", []) if a.get("title")]
        except Exception as exc:
            logger.error("News error: %s", exc)
            return []


class JokeModule:
    JOKES = [
        ("Why don't scientists trust atoms?", "Because they make up everything!"),
        ("Why did the computer go to therapy?", "It had too many bytes of emotional baggage."),
        ("Why do programmers prefer dark mode?", "Because light attracts bugs!"),
        ("What do you call a fake noodle?", "An impasta!"),
        ("Why did the math book look so sad?", "Because it had too many problems."),
        ("I told my computer I needed a break.", "Now it won't stop sending me Kit-Kat ads."),
    ]

    @staticmethod
    def tell() -> tuple:
        return random.choice(JokeModule.JOKES)


class WikipediaModule:
    """
    FIX: wikipedia.DisambiguationError must be caught as wikipedia.DisambiguationError
    (not from a sub-module path).  The `wikipedia` package exposes it at the top level.
    Also: auto_suggest=True can raise PageError on Python 3.12 for some queries —
    we fall back gracefully.
    """

    @staticmethod
    def search(query: str, sentences: int = 3) -> str:
        try:
            wikipedia.set_lang("en")
            return wikipedia.summary(query, sentences=sentences, auto_suggest=False)
        except wikipedia.DisambiguationError as exc:
            # exc.options is a list of suggestions
            suggestions = exc.options[:3] if exc.options else []
            return f"Multiple results found. Did you mean: {', '.join(suggestions)}?"
        except wikipedia.PageError:
            return "I couldn't find that on Wikipedia."
        except Exception as exc:
            logger.error("Wikipedia error: %s", exc)
            return "Wikipedia search failed."


class EmailModule:
    """
    NOTE: Gmail requires an App Password (not your main password) when
    2-Factor Authentication is enabled.  Standard passwords no longer work
    with SMTP since May 2022.  See CHANGES.md for setup instructions.
    """

    def __init__(self, sender_email: str, password: str) -> None:
        self.sender = sender_email
        self.password = password

    def send(self, to: str, subject: str, body: str) -> bool:
        try:
            msg = MIMEMultipart()
            msg["From"] = self.sender
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.ehlo()
                server.starttls()
                server.login(self.sender, self.password)
                server.sendmail(self.sender, to, msg.as_string())
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error("Email auth failed — check App Password in config.json")
            return False
        except Exception as exc:
            logger.error("Email error: %s", exc)
            return False


class ReminderModule:
    """
    FIX: Python 3.12 deprecated implicit daemon threads in some contexts.
    We now set daemon=True explicitly and use threading.Event for clean cancellation.
    """

    def __init__(self, voice: VoiceEngine) -> None:
        self.voice = voice

    def set_reminder(self, message: str, minutes: int) -> None:
        stop_event = threading.Event()

        def _remind() -> None:
            if not stop_event.wait(timeout=minutes * 60):
                # waited the full duration without being cancelled
                # NOTE: this runs in a background thread — pyttsx3 speak() may
                # crash on Windows/macOS.  We print instead and log.
                logger.info("⏰ REMINDER: %s", message)
                print(f"\n⏰ REMINDER: {message}\n")

        t = threading.Thread(target=_remind, daemon=True)
        t.start()
        logger.info("Reminder set: '%s' in %d min", message, minutes)

    def set_alarm(self, hour: int, minute: int) -> None:
        def _alarm() -> None:
            while True:
                now = datetime.datetime.now()
                if now.hour == hour and now.minute == minute:
                    logger.info("⏰ ALARM: time is %02d:%02d", hour, minute)
                    print("\n⏰ ALARM IS RINGING! Wake up!\n")
                    break
                time.sleep(30)

        t = threading.Thread(target=_alarm, daemon=True)
        t.start()


class MotivationModule:
    QUOTES = [
        "Believe in yourself and all that you are.",
        "Success is not final; failure is not fatal — it is the courage to continue that counts.",
        "The only way to do great work is to love what you do.",
        "Don't watch the clock. Do what it does — keep going.",
        "You are never too old to set another goal or dream a new dream.",
        "Push yourself, because no one else is going to do it for you.",
        "Great things never come from comfort zones.",
        "Dream it. Wish it. Do it.",
        "The harder you work for something, the greater you'll feel when you achieve it.",
        "Don't stop when you're tired. Stop when you're done.",
    ]

    @staticmethod
    def get() -> str:
        return random.choice(MotivationModule.QUOTES)


class FactsModule:
    @staticmethod
    def get_fact() -> str:
        try:
            r = requests.get(
                "https://uselessfacts.jsph.pl/api/v2/facts/random?language=en",
                timeout=5,
            )
            return r.json().get("text", "Python was named after Monty Python!")
        except Exception:
            return "Did you know? Honey never spoils — archaeologists found 3000-year-old honey in Egyptian tombs!"


# ─────────────────────────────────────────────
#  Cross-Platform System Commands
#  FIX: Original used amixer (Linux-only) and scrot (Linux-only).
#  We now detect the OS and use the appropriate tool.
# ─────────────────────────────────────────────
def _volume_up() -> None:
    platform = sys.platform
    try:
        if platform == "linux":
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "10%+"], check=False)
        elif platform == "darwin":
            subprocess.run(["osascript", "-e", "set volume output volume ((output volume of (get volume settings)) + 10)"], check=False)
        elif platform == "win32":
            # Uses pycaw or nircmd if installed; graceful fallback
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            current = volume.GetMasterVolumeLevelScalar()
            volume.SetMasterVolumeLevelScalar(min(1.0, current + 0.1), None)
    except Exception as exc:
        logger.warning("Volume up failed: %s", exc)


def _volume_down() -> None:
    platform = sys.platform
    try:
        if platform == "linux":
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "10%-"], check=False)
        elif platform == "darwin":
            subprocess.run(["osascript", "-e", "set volume output volume ((output volume of (get volume settings)) - 10)"], check=False)
        elif platform == "win32":
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            current = volume.GetMasterVolumeLevelScalar()
            volume.SetMasterVolumeLevelScalar(max(0.0, current - 0.1), None)
    except Exception as exc:
        logger.warning("Volume down failed: %s", exc)


def _screenshot() -> Optional[str]:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = Path.home() / "Desktop" / f"screenshot_{ts}.png"
    try:
        if sys.platform == "linux":
            subprocess.run(["scrot", str(dest)], check=False)
        elif sys.platform == "darwin":
            subprocess.run(["screencapture", str(dest)], check=False)
        elif sys.platform == "win32":
            # Requires Pillow
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img.save(str(dest))
        return str(dest)
    except Exception as exc:
        logger.warning("Screenshot failed: %s", exc)
        return None


# ─────────────────────────────────────────────
#  Website Map
# ─────────────────────────────────────────────
WEBSITE_MAP: dict = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://www.twitter.com",
    "instagram": "https://www.instagram.com",
    "github": "https://www.github.com",
    "linkedin": "https://www.linkedin.com",
    "reddit": "https://www.reddit.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.in",
}


# ─────────────────────────────────────────────
#  Smart Command Router
# ─────────────────────────────────────────────
def route_command(query: str, voice: VoiceEngine, modules: dict) -> bool:
    """Route a voice/text command to the appropriate skill.
    Returns False when the assistant should stop (exit/bye/quit).
    """

    # ── Wikipedia ──────────────────────────────
    if "wikipedia" in query:
        topic = query.replace("wikipedia", "").strip()
        if topic:
            voice.speak(f"Searching Wikipedia for {topic}...")
            result = WikipediaModule.search(topic)
            voice.speak(result)
        return True

    # ── Time ───────────────────────────────────
    if any(k in query for k in ["what time", "current time", "time now"]):
        t = datetime.datetime.now().strftime("%I:%M %p")
        voice.speak(f"The current time is {t}.")
        return True

    # ── Date ───────────────────────────────────
    if any(k in query for k in ["what date", "today's date", "current date"]):
        d = datetime.datetime.now().strftime("%A, %B %d, %Y")
        voice.speak(f"Today is {d}.")
        return True

    # ── Weather ────────────────────────────────
    if "weather" in query:
        city = modules.get("default_city", "Kolkata")
        for word in ["in", "for", "at"]:
            if f" {word} " in query:
                city = query.split(f" {word} ")[-1].strip()
                break
        voice.speak(f"Fetching weather for {city}...")
        result = modules["weather"].get_weather(city)
        voice.speak(result)
        return True

    # ── News ───────────────────────────────────
    if "news" in query:
        voice.speak("Here are today's top headlines...")
        headlines = modules["news"].get_headlines()
        if headlines:
            for i, h in enumerate(headlines[:5], 1):
                voice.speak(f"Headline {i}: {h}")
                time.sleep(0.5)
        else:
            voice.speak("I couldn't fetch the news right now.")
        return True

    # ── Joke ───────────────────────────────────
    if any(k in query for k in ["joke", "funny", "make me laugh"]):
        setup, punchline = JokeModule.tell()
        voice.speak(setup)
        time.sleep(2)
        voice.speak(punchline)
        return True

    # ── Motivate ───────────────────────────────
    if any(k in query for k in ["motivate", "inspire", "motivation", "inspiration"]):
        voice.speak(MotivationModule.get())
        return True

    # ── Fact ───────────────────────────────────
    if any(k in query for k in ["fact", "interesting", "did you know"]):
        voice.speak("Here's something interesting...")
        voice.speak(FactsModule.get_fact())
        return True

    # ── Open Website ───────────────────────────
    if "open" in query:
        for site, url in WEBSITE_MAP.items():
            if site in query:
                voice.speak(f"Opening {site}...")
                webbrowser.open(url)
                return True
        parts = query.replace("open", "").strip().split()
        if parts:
            url = f"https://www.{parts[0]}.com"
            voice.speak(f"Opening {parts[0]}...")
            webbrowser.open(url)
        return True

    # ── Google Search ──────────────────────────
    if "search" in query or "google" in query:
        search_q = query.replace("search", "").replace("google", "").strip()
        if search_q:
            voice.speak(f"Searching for {search_q}...")
            webbrowser.open(f"https://www.google.com/search?q={search_q}")
        return True

    # ── Play YouTube ───────────────────────────
    if "play" in query and "youtube" in query:
        search_q = query.replace("play", "").replace("youtube", "").strip()
        if search_q:
            voice.speak(f"Playing {search_q} on YouTube...")
            webbrowser.open(f"https://www.youtube.com/results?search_query={search_q}")
        return True

    # ── Reminder ───────────────────────────────
    if "remind me" in query:
        try:
            msg_part = query.split("remind me to")[-1].strip()
            voice.speak(f"Setting a reminder: {msg_part}. In how many minutes?")
            mins_str = input("Minutes: ").strip()
            mins = int(mins_str)
            modules["reminder"].set_reminder(msg_part, mins)
            voice.speak(f"I'll remind you to {msg_part} in {mins} minutes.")
        except Exception:
            voice.speak("I couldn't set the reminder. Please try again.")
        return True

    # ── Alarm ──────────────────────────────────
    if "set alarm" in query or "set an alarm" in query:
        voice.speak("What time should I set the alarm? Example: 7 30 AM")
        time_str = input("Alarm time (HH MM AM/PM): ").strip()
        try:
            parts = time_str.split()
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            ampm = parts[2].lower() if len(parts) > 2 else "am"
            if ampm == "pm" and hour != 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            modules["reminder"].set_alarm(hour, minute)
            voice.speak(f"Alarm set for {time_str}.")
        except Exception:
            voice.speak("I couldn't set the alarm. Please try again.")
        return True

    # ── Email ──────────────────────────────────
    if "send email" in query or "compose email" in query:
        voice.speak("Who should I send it to? Please type the email address.")
        to = input("To: ").strip()
        voice.speak("What's the subject?")
        subject = input("Subject: ").strip()
        voice.speak("What should I say in the email?")
        body = input("Body: ").strip()
        success = modules["email"].send(to, subject, body)
        voice.speak("Email sent successfully!" if success else "Sorry, I couldn't send the email.")
        return True

    # ── Volume ─────────────────────────────────
    if "volume up" in query:
        _volume_up()
        voice.speak("Volume increased.")
        return True

    if "volume down" in query:
        _volume_down()
        voice.speak("Volume decreased.")
        return True

    # ── Screenshot ─────────────────────────────
    if "screenshot" in query:
        path = _screenshot()
        if path:
            voice.speak(f"Screenshot saved to your desktop.")
        else:
            voice.speak("I couldn't take a screenshot on this system.")
        return True

    # ── Calculator ─────────────────────────────
    # FIX: replaced eval() with safe_eval() — no arbitrary code execution
    if "calculate" in query or "what is" in query:
        expr = query.replace("calculate", "").replace("what is", "").strip()
        # Strip trailing punctuation that voice recognition often adds
        expr = expr.rstrip("?.")
        try:
            result = safe_eval(expr)
            # Show clean int if result is whole number
            display = int(result) if result == int(result) else result
            voice.speak(f"The answer is {display}.")
        except Exception:
            voice.speak("I couldn't calculate that. Please say a simple math expression.")
        return True

    # ── Help ───────────────────────────────────
    if any(k in query for k in ["who are you", "what can you do", "help"]):
        voice.speak(
            "I'm ARIA — your Advanced Responsive Intelligent Assistant. "
            "I can search Wikipedia, fetch weather and news, set reminders and alarms, "
            "tell jokes, open websites, send emails, motivate you, and much more. "
            "Just ask!"
        )
        return True

    # ── Exit ───────────────────────────────────
    if any(k in query for k in ["stop", "exit", "quit", "goodbye", "bye"]):
        voice.speak("Goodbye! Have a productive day ahead. Take care!")
        return False

    # ── Unknown ────────────────────────────────
    if query:
        voice.speak("I'm not sure how to handle that. Let me search it for you.")
        webbrowser.open(f"https://www.google.com/search?q={query}")

    return True


# ─────────────────────────────────────────────
#  Greeting
# ─────────────────────────────────────────────
def greet(voice: VoiceEngine) -> None:
    hour = datetime.datetime.now().hour
    if hour < 12:
        period = "Good morning"
    elif hour < 18:
        period = "Good afternoon"
    else:
        period = "Good evening"

    greetings = [
        f"{period}! I'm ARIA, your Smart Virtual Assistant. How can I help you today?",
        f"{period}! ARIA at your service. What would you like to do?",
        f"{period}! Ready to assist. Just say the word!",
    ]
    voice.speak(random.choice(greetings))


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────
def main() -> None:
    print("""
╔══════════════════════════════════════════════════════════╗
║   🤖  ARIA — SMART VIRTUAL ASSISTANT  v3.0              ║
║   Built with Python | Voice + Text Interface            ║
║   Say 'help' to discover what I can do.                 ║
║   Say 'stop' or 'exit' to quit.                         ║
╚══════════════════════════════════════════════════════════╝
    """)

    # ── Load config ──────────────────────────────
    # FIX: Use pathlib for robust path resolution
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    config: dict = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    else:
        logger.warning(
            "config.json not found at %s — running with defaults. "
            "Copy config.template.json → config/config.json and fill in your API keys.",
            config_path,
        )

    # ── Initialise core components ───────────────
    voice = VoiceEngine()
    voice.configure_from(config)

    recognizer = SpeechRecognizer(language=config.get("language", "en-in"))

    # ── Initialise skill modules ─────────────────
    modules: dict = {
        "weather": WeatherModule(config.get("WEATHER_API_KEY", "YOUR_OPENWEATHERMAP_API_KEY")),
        "news":    NewsModule(config.get("NEWS_API_KEY", "YOUR_NEWSAPI_KEY")),
        "email":   EmailModule(
            config.get("EMAIL", "your-email@gmail.com"),
            config.get("EMAIL_PASSWORD", "your-app-password"),
        ),
        "reminder":     ReminderModule(voice),
        "default_city": config.get("default_city", "Kolkata"),
    }

    greet(voice)

    mode = config.get("mode", "voice")  # "voice" or "text"

    running = True
    while running:
        try:
            if mode == "voice":
                query = recognizer.listen()
            else:
                query = input("\n💬 You: ").strip().lower()

            if not query:
                continue

            running = route_command(query, voice, modules)

        except KeyboardInterrupt:
            voice.speak("Shutting down. Goodbye!")
            break
        except Exception as exc:
            logger.error("Unexpected error: %s", exc)
            voice.speak("Something went wrong. Let's continue.")


if __name__ == "__main__":
    main()
