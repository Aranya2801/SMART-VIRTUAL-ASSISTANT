"""
╔══════════════════════════════════════════════════════════════╗
║           SMART VIRTUAL ASSISTANT — Core Engine              ║
║           Author: Aranya Ghosh | KIIT University             ║
║           Version: 2.0.0 | Python 3.10+                      ║
╚══════════════════════════════════════════════════════════════╝
"""

import speech_recognition as sr
import pyttsx3
import datetime
import wikipedia
import webbrowser
import os
import smtplib
import random
import requests
import time
import json
import logging
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

# ─────────────────────────────────────────────
#  Logging Configuration
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("assistant.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Voice Engine Setup
# ─────────────────────────────────────────────
class VoiceEngine:
    def __init__(self):
        self.engine = pyttsx3.init()
        self._configure()

    def _configure(self):
        voices = self.engine.getProperty('voices')
        # Prefer female voice (index 1) if available
        if len(voices) > 1:
            self.engine.setProperty('voice', voices[1].id)
        self.engine.setProperty('rate', 170)      # Speed: words per minute
        self.engine.setProperty('volume', 0.95)   # Volume: 0.0 to 1.0

    def speak(self, text: str):
        """Convert text to speech and print to console."""
        logger.info(f"[ASSISTANT]: {text}")
        print(f"\n🤖 ARIA: {text}\n")
        self.engine.say(text)
        self.engine.runAndWait()


# ─────────────────────────────────────────────
#  Speech Recognizer
# ─────────────────────────────────────────────
class SpeechRecognizer:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1
        self.recognizer.energy_threshold = 300

    def listen(self) -> str:
        """Listen from microphone and return recognized text."""
        with sr.Microphone() as source:
            print("\n🎤 Listening...", end="", flush=True)
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=10)
                print(" Done!")
                query = self.recognizer.recognize_google(audio, language='en-in')
                logger.info(f"[USER]: {query}")
                print(f"👤 You: {query}")
                return query.lower()
            except sr.WaitTimeoutError:
                return ""
            except sr.UnknownValueError:
                print(" (could not understand)")
                return ""
            except sr.RequestError as e:
                logger.error(f"Speech recognition error: {e}")
                return ""


# ─────────────────────────────────────────────
#  Skill Modules
# ─────────────────────────────────────────────
class WeatherModule:
    BASE_URL = "http://api.openweathermap.org/data/2.5/weather"

    def __init__(self, api_key: str):
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
        except Exception as e:
            logger.error(f"Weather error: {e}")
            return "Unable to fetch weather data right now."


class NewsModule:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_headlines(self, country: str = "in", count: int = 5) -> list[str]:
        try:
            url = (
                f"https://newsapi.org/v2/top-headlines"
                f"?country={country}&pageSize={count}&apiKey={self.api_key}"
            )
            data = requests.get(url, timeout=5).json()
            return [a["title"] for a in data.get("articles", []) if a.get("title")]
        except Exception as e:
            logger.error(f"News error: {e}")
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
    def tell() -> tuple[str, str]:
        return random.choice(JokeModule.JOKES)


class WikipediaModule:
    @staticmethod
    def search(query: str, sentences: int = 3) -> str:
        try:
            wikipedia.set_lang("en")
            return wikipedia.summary(query, sentences=sentences, auto_suggest=True)
        except wikipedia.DisambiguationError as e:
            return f"Multiple results found. Did you mean: {e.options[0]}?"
        except wikipedia.PageError:
            return "I couldn't find that on Wikipedia."
        except Exception as e:
            logger.error(f"Wikipedia error: {e}")
            return "Wikipedia search failed."


class EmailModule:
    def __init__(self, sender_email: str, password: str):
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
        except Exception as e:
            logger.error(f"Email error: {e}")
            return False


class ReminderModule:
    def __init__(self, voice: VoiceEngine):
        self.voice = voice
        self.reminders: list[dict] = []

    def set_reminder(self, message: str, minutes: int):
        def _remind():
            time.sleep(minutes * 60)
            self.voice.speak(f"⏰ Reminder: {message}")

        t = threading.Thread(target=_remind, daemon=True)
        t.start()
        logger.info(f"Reminder set: '{message}' in {minutes} min")

    def set_alarm(self, hour: int, minute: int):
        def _alarm():
            while True:
                now = datetime.datetime.now()
                if now.hour == hour and now.minute == minute:
                    self.voice.speak("⏰ Your alarm is ringing! Wake up!")
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
            r = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en", timeout=5)
            return r.json().get("text", "Here's a fact: Python was named after Monty Python!")
        except Exception:
            return "Did you know? Honey never spoils — archaeologists have found 3000-year-old honey in Egyptian tombs!"


# ─────────────────────────────────────────────
#  Smart Command Router
# ─────────────────────────────────────────────
WEBSITE_MAP = {
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


def route_command(query: str, voice: VoiceEngine, modules: dict) -> bool:
    """
    Route a voice/text command to the appropriate skill module.
    Returns False if 'stop' or 'exit' command received.
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
        city = "Kolkata"
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
        # Generic open
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
        voice.speak("What time should I set the alarm for? Say hour and minute.")
        voice.speak("For example: 7 30 AM")
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
        if success:
            voice.speak("Email sent successfully!")
        else:
            voice.speak("Sorry, I couldn't send the email.")
        return True

    # ── System ─────────────────────────────────
    if "volume up" in query:
        os.system("amixer -D pulse sset Master 10%+")
        voice.speak("Volume increased.")
        return True

    if "volume down" in query:
        os.system("amixer -D pulse sset Master 10%-")
        voice.speak("Volume decreased.")
        return True

    if "screenshot" in query:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        os.system(f"scrot ~/Desktop/screenshot_{ts}.png")
        voice.speak("Screenshot saved to your desktop.")
        return True

    # ── Calculator ─────────────────────────────
    if "calculate" in query or "what is" in query:
        expr = query.replace("calculate", "").replace("what is", "").strip()
        try:
            result = eval(expr, {"__builtins__": {}})
            voice.speak(f"The answer is {result}.")
        except Exception:
            voice.speak("I couldn't calculate that. Please try again.")
        return True

    # ── Greet / About ──────────────────────────
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
        voice.speak(f"I'm not sure how to handle that. Let me search it for you.")
        webbrowser.open(f"https://www.google.com/search?q={query}")

    return True


# ─────────────────────────────────────────────
#  Greeting Logic
# ─────────────────────────────────────────────
def greet(voice: VoiceEngine):
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
def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║   🤖  ARIA — SMART VIRTUAL ASSISTANT  v2.0              ║
║   Built with Python | Voice + Text Interface            ║
║   Say 'help' to discover what I can do.                 ║
║   Say 'stop' or 'exit' to quit.                         ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Load config
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
    config = {}
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)

    # Initialize core components
    voice = VoiceEngine()
    recognizer = SpeechRecognizer()

    # Initialize skill modules
    modules = {
        "weather": WeatherModule(config.get("WEATHER_API_KEY", "YOUR_OPENWEATHER_API_KEY")),
        "news":    NewsModule(config.get("NEWS_API_KEY", "YOUR_NEWSAPI_KEY")),
        "email":   EmailModule(
            config.get("EMAIL", "your-email@gmail.com"),
            config.get("EMAIL_PASSWORD", "your-app-password")
        ),
        "reminder": ReminderModule(voice),
    }

    greet(voice)

    # Main interaction loop
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
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            voice.speak("Something went wrong. Let's continue.")


if __name__ == "__main__":
    main()
