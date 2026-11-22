"""What ARIA can actually do once it knows the intent.

Each handler gets the filled slots and returns either a string to say, an
Ask (a required slot is missing) or a Confirm (we want a yes/no first, e.g.
before sending an email). External things (HTTP, the browser, the clock) are
passed in so the handlers can be tested without network or a desktop.
"""

from __future__ import annotations

import logging
import platform
import random
import shutil
import smtplib
import subprocess
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Callable
from urllib.parse import quote, quote_plus

import requests

from . import calc
from .config import Settings
from .scheduler import Scheduler

log = logging.getLogger(__name__)


@dataclass
class Ask:
    slot: str
    prompt: str


@dataclass
class Confirm:
    prompt: str
    on_yes: Callable[[], str]
    on_no: str = "Okay, cancelled."


@dataclass
class Context:
    settings: Settings
    say: Callable[[str], None]
    scheduler: Scheduler
    http: requests.Session = field(default_factory=requests.Session)
    open_url: Callable[[str], object] = webbrowser.open
    now: Callable[[], datetime] = datetime.now


SITES = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "linkedin": "https://www.linkedin.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack": "https://stackoverflow.com",
    "reddit": "https://www.reddit.com",
    "wikipedia": "https://en.wikipedia.org",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.in",
    "spotify": "https://open.spotify.com",
    "whatsapp": "https://web.whatsapp.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "instagram": "https://www.instagram.com",
}

JOKES = [
    ("Why do programmers prefer dark mode?", "Because light attracts bugs."),
    ("Why did the developer go broke?", "He used up all his cache."),
    ("How many programmers does it take to change a light bulb?", "None. That's a hardware problem."),
    ("What's a computer's favourite snack?", "Microchips."),
    ("Why was the maths book sad?", "It had too many problems."),
    ("I told my laptop I needed a break.", "It said no problem, it would go to sleep."),
    ("Why don't scientists trust atoms?", "They make up everything."),
]

QUOTES = [
    "Small steps every day add up. - unknown",
    "It always seems impossible until it's done. - Nelson Mandela",
    "The secret of getting ahead is getting started. - Mark Twain",
    "Don't watch the clock; do what it does. Keep going. - Sam Levenson",
    "Done is better than perfect. - Sheryl Sandberg",
    "You don't have to be great to start, but you have to start to be great. - Zig Ziglar",
]

OFFLINE_FACTS = [
    "Honey found in ancient Egyptian tombs was still edible.",
    "Octopuses have three hearts.",
    "The first computer bug was an actual moth, found in a Harvard Mark II relay in 1947.",
    "A day on Venus is longer than a year on Venus.",
]


def _say_time(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def _say_duration(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h} hour{'s' if h != 1 else ''}")
    if m:
        parts.append(f"{m} minute{'s' if m != 1 else ''}")
    if s and not h:
        parts.append(f"{s} second{'s' if s != 1 else ''}")
    return " and ".join(parts) or "0 seconds"


# --- handlers ---------------------------------------------------------------

def greeting(ctx: Context, slots: dict) -> str:
    h = ctx.now().hour
    part = "morning" if h < 12 else "afternoon" if h < 17 else "evening"
    return f"Good {part}! What can I do for you?"


def goodbye(ctx: Context, slots: dict) -> str:
    return "Bye! Talk to you later."


def help_(ctx: Context, slots: dict) -> str:
    return ("I can tell you the time, date and weather, read the news, look things up on "
            "Wikipedia, set reminders, timers and alarms, do quick maths, open websites, "
            "play music on YouTube, send an email, and tell you a joke if you need one.")


def about(ctx: Context, slots: dict) -> str:
    return ("I'm ARIA, a small open-source voice assistant written in Python. "
            "I run on your own machine and only use the internet for things like weather and search.")


def time_(ctx: Context, slots: dict) -> str:
    return f"It's {_say_time(ctx.now())}."


def date_(ctx: Context, slots: dict) -> str:
    return f"Today is {ctx.now().strftime('%A, %d %B %Y')}."


def weather(ctx: Context, slots: dict) -> str:
    city = slots.get("city") or ctx.settings.default_city
    key = ctx.settings.weather_api_key
    if not key:
        return "Weather isn't set up yet. Add an OpenWeatherMap key as ARIA_WEATHER_API_KEY."
    try:
        r = ctx.http.get("https://api.openweathermap.org/data/2.5/weather",
                         params={"q": city, "appid": key, "units": "metric"}, timeout=6)
        data = r.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("weather request failed: %s", exc)
        return "I couldn't reach the weather service."
    if str(data.get("cod")) != "200":
        return f"I couldn't find weather for {city}."
    desc = data["weather"][0]["description"]
    temp = round(data["main"]["temp"])
    feels = round(data["main"]["feels_like"])
    hum = data["main"]["humidity"]
    msg = f"In {data.get('name', city)} it's {temp} degrees with {desc}"
    if abs(feels - temp) >= 2:
        msg += f", feels like {feels}"
    return msg + f". Humidity is {hum} percent."


def news(ctx: Context, slots: dict) -> str:
    key = ctx.settings.news_api_key
    if not key:
        return "News isn't set up yet. Add a NewsAPI key as ARIA_NEWS_API_KEY."
    try:
        r = ctx.http.get("https://newsapi.org/v2/top-headlines",
                         params={"country": ctx.settings.news_country, "pageSize": 5},
                         headers={"X-Api-Key": key}, timeout=6)
        data = r.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("news request failed: %s", exc)
        return "I couldn't reach the news service."
    titles = [a["title"].rsplit(" - ", 1)[0] for a in data.get("articles", []) if a.get("title")]
    if not titles:
        return "I didn't get any headlines back."
    lines = [f"{i}. {t}." for i, t in enumerate(titles, 1)]
    return "Here are the top headlines. " + " ".join(lines)


def definition(ctx: Context, slots: dict):
    topic = slots.get("topic")
    if not topic:
        return Ask("topic", "What should I look up?")
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(topic.replace(" ", "_"))
    try:
        r = ctx.http.get(url, timeout=6, headers={"User-Agent": "ARIA-assistant/3.0"})
        if r.status_code == 404:
            # try the search API to fix the title, e.g. "alan turing" -> "Alan Turing"
            s = ctx.http.get("https://en.wikipedia.org/w/api.php", timeout=6, params={
                "action": "opensearch", "search": topic, "limit": 1, "format": "json"}).json()
            if not s[1]:
                return f"I couldn't find anything on Wikipedia about {topic}."
            r = ctx.http.get("https://en.wikipedia.org/api/rest_v1/page/summary/"
                             + quote(s[1][0].replace(" ", "_")), timeout=6)
        data = r.json()
    except (requests.RequestException, ValueError, IndexError) as exc:
        log.warning("wikipedia failed: %s", exc)
        return "Wikipedia isn't responding right now."
    if data.get("type") == "disambiguation":
        return f"'{topic}' could mean a few different things. Can you be more specific?"
    extract = data.get("extract", "").strip()
    if not extract:
        return f"I couldn't find a summary for {topic}."
    # keep it to roughly two sentences, nobody wants a page read out loud
    sentences = extract.split(". ")
    return ". ".join(sentences[:2]).rstrip(".") + "."


def fun_fact(ctx: Context, slots: dict) -> str:
    try:
        r = ctx.http.get("https://uselessfacts.jsph.pl/api/v2/facts/random",
                         params={"language": "en"}, timeout=4)
        text = r.json().get("text")
        if text:
            return text.strip()
    except (requests.RequestException, ValueError):
        pass
    return random.choice(OFFLINE_FACTS)


def joke(ctx: Context, slots: dict) -> str:
    setup, punch = random.choice(JOKES)
    return f"{setup} ... {punch}"


def motivation(ctx: Context, slots: dict) -> str:
    return random.choice(QUOTES)


def calculator(ctx: Context, slots: dict) -> str:
    try:
        value = calc.evaluate(slots.get("expression", ""))
    except calc.CalcError:
        return "Sorry, I couldn't work that one out. Try something like 'what is 12 times 7'."
    return f"That's {calc.format_number(value)}."


def reminder(ctx: Context, slots: dict):
    if not slots.get("message"):
        return Ask("message", "What should I remind you about?")
    if not slots.get("seconds") and not slots.get("at"):
        return Ask("when", "When? For example 'in 20 minutes' or 'at 6 pm'.")
    msg = slots["message"]
    fire = lambda job: ctx.say(f"Reminder: {msg}.")  # noqa: E731
    if slots.get("seconds"):
        ctx.scheduler.add(slots["seconds"], "reminder", msg, fire)
        return f"Okay, I'll remind you to {msg} in {_say_duration(slots['seconds'])}."
    ctx.scheduler.add_at(slots["at"], "reminder", msg, fire)
    return f"Okay, I'll remind you to {msg} at {_say_time(slots['at'])}."


def timer(ctx: Context, slots: dict):
    secs = slots.get("seconds")
    if not secs:
        return Ask("seconds", "For how long?")
    ctx.scheduler.add(secs, "timer", _say_duration(secs),
                      lambda job: ctx.say(f"Your {job.label} timer is done."))
    return f"Timer set for {_say_duration(secs)}."


def alarm(ctx: Context, slots: dict):
    at = slots.get("at")
    if not at:
        return Ask("at", "What time should I set the alarm for?")
    ctx.scheduler.add_at(at, "alarm", _say_time(at),
                         lambda job: ctx.say(f"It's {job.label}. This is your alarm!"))
    day = "tomorrow" if at.date() != ctx.now().date() else "today"
    return f"Alarm set for {_say_time(at)} {day}."


def open_website(ctx: Context, slots: dict):
    site = slots.get("site")
    if not site:
        return Ask("site", "Which website?")
    site = site.lower().removeprefix("www.")
    if site in SITES:
        url = SITES[site]
    elif "." in site:
        url = "https://" + site
    else:
        # don't guess https://www.<word>.com like before, that can land on
        # a squatted domain. Search instead.
        url = "https://duckduckgo.com/?q=!" + quote_plus(site)
    ctx.open_url(url)
    return f"Opening {site}."


def web_search(ctx: Context, slots: dict):
    q = slots.get("query")
    if not q:
        return Ask("query", "What should I search for?")
    ctx.open_url("https://www.google.com/search?q=" + quote_plus(q))
    return f"Here's what I found for {q}."


def play_music(ctx: Context, slots: dict):
    song = slots.get("song") or "lofi music"
    ctx.open_url("https://www.youtube.com/results?search_query=" + quote_plus(song))
    return f"Playing {song} on YouTube."


def _run(cmd: list[str]) -> bool:
    if not shutil.which(cmd[0]):
        return False
    return subprocess.run(cmd, capture_output=True).returncode == 0


def volume(ctx: Context, slots: dict):
    direction = slots.get("direction")
    if not direction:
        return Ask("direction", "Up, down or mute?")
    system = platform.system()
    ok = False
    if system == "Linux":
        arg = {"up": "+10%", "down": "-10%", "mute": "toggle"}[direction]
        ok = (_run(["pactl", "set-sink-mute" if direction == "mute" else "set-sink-volume",
                    "@DEFAULT_SINK@", arg])
              or _run(["amixer", "-q", "sset", "Master", "toggle" if direction == "mute"
                       else arg.replace("+", "").replace("-", "") + ("+" if direction == "up" else "-")]))
    elif system == "Darwin":
        script = {"up": "set volume output volume ((output volume of (get volume settings)) + 10)",
                  "down": "set volume output volume ((output volume of (get volume settings)) - 10)",
                  "mute": "set volume output muted not (output muted of (get volume settings))"}
        ok = _run(["osascript", "-e", script[direction]])
    elif system == "Windows":
        ok = _windows_volume(direction)
    if not ok:
        return "I couldn't change the volume on this system."
    return {"up": "Turned it up.", "down": "Turned it down.", "mute": "Toggled mute."}[direction]


def _windows_volume(direction: str) -> bool:
    try:
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    except ImportError:
        return False
    dev = AudioUtilities.GetSpeakers()
    vol = cast(dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))
    if direction == "mute":
        vol.SetMute(not vol.GetMute(), None)
    else:
        cur = vol.GetMasterVolumeLevelScalar()
        step = 0.1 if direction == "up" else -0.1
        vol.SetMasterVolumeLevelScalar(min(1.0, max(0.0, cur + step)), None)
    return True


def screenshot(ctx: Context, slots: dict) -> str:
    try:
        from PIL import ImageGrab
    except ImportError:
        return "Screenshots need Pillow installed (pip install pillow)."
    folder = Path.home() / "Pictures"
    folder.mkdir(exist_ok=True)
    path = folder / f"screenshot_{ctx.now():%Y%m%d_%H%M%S}.png"
    try:
        ImageGrab.grab().save(path)
    except OSError as exc:
        log.warning("screenshot failed: %s", exc)
        return "I couldn't take a screenshot here."
    return f"Saved a screenshot to {path.parent.name}/{path.name}."


def send_email(ctx: Context, slots: dict):
    s = ctx.settings
    if not (s.email and s.email_password):
        return "Email isn't set up. Add ARIA_EMAIL and an app password as ARIA_EMAIL_PASSWORD."
    for slot, prompt in (("to", "Who's it for? Say or type the email address."),
                         ("subject", "What's the subject?"),
                         ("body", "And what should it say?")):
        if not slots.get(slot):
            return Ask(slot, prompt)

    def _send() -> str:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = s.email, slots["to"], slots["subject"]
        msg.set_content(slots["body"])
        try:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(s.email, s.email_password)
                server.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            log.warning("email failed: %s", exc)
            return "Sending failed. Check the email settings."
        return "Sent."

    return Confirm(f"Send '{slots['subject']}' to {slots['to']}?", _send)


def list_jobs(ctx: Context, slots: dict) -> str:
    jobs = ctx.scheduler.pending()
    if not jobs:
        return "You don't have any reminders or alarms."
    return "You have " + "; ".join(f"{j.kind} '{j.label}' at {_say_time(j.due_dt)}" for j in jobs) + "."


HANDLERS: dict[str, Callable] = {
    "greeting": greeting, "goodbye": goodbye, "help": help_, "about": about,
    "time": time_, "date": date_, "weather": weather, "news": news,
    "definition": definition, "fun_fact": fun_fact, "joke": joke, "motivation": motivation,
    "calculator": calculator, "reminder": reminder, "list_reminders": list_jobs,
    "timer": timer, "alarm": alarm,
    "open_website": open_website, "web_search": web_search, "play_music": play_music,
    "volume": volume, "screenshot": screenshot, "send_email": send_email,
}
