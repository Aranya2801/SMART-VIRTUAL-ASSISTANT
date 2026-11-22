"""Slot extraction with regexes.

Small and boring on purpose. Each extractor returns a dict that is empty when
nothing was found, and the dialogue manager asks a follow-up question for
whatever required slot is still missing.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

_NUM_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15,
    "twenty": 20, "thirty": 30, "forty": 40, "forty five": 45, "fifty": 50,
    "sixty": 60, "ninety": 90, "half an": 0.5, "half a": 0.5,
}
_UNIT_SECONDS = {"second": 1, "sec": 1, "minute": 60, "min": 60, "hour": 3600, "hr": 3600}

_num_alt = "|".join(sorted(map(re.escape, _NUM_WORDS), key=len, reverse=True))
_DURATION_RE = re.compile(
    rf"(?P<n>\d+(?:\.\d+)?|{_num_alt})\s*(?P<unit>hours?|hrs?|minutes?|mins?|seconds?|secs?)\b"
)

_CLOCK_RE = re.compile(
    r"\b(?P<h>\d{1,2})(?:[:. ](?P<m>\d{2}))?\s*(?P<ampm>a\.?m\.?|p\.?m\.?)?(?=\s|$|[^\w])"
)


def _to_number(s: str) -> float:
    s = s.strip()
    return float(s) if s[0].isdigit() else float(_NUM_WORDS[s])


def duration_seconds(text: str) -> int | None:
    """'in 1 hour and 20 minutes' -> 4800. None if no duration found."""
    total = 0.0
    found = False
    for m in _DURATION_RE.finditer(text.lower()):
        unit = m.group("unit").rstrip("s")
        unit = {"hr": "hour", "min": "minute", "sec": "second"}.get(unit, unit)
        total += _to_number(m.group("n")) * _UNIT_SECONDS[unit]
        found = True
    if not found and re.search(r"\bhalf an hour\b", text.lower()):
        return 1800
    return int(total) if found else None


def clock_time(text: str, now: datetime | None = None) -> datetime | None:
    """Parse '7:30 am', '6 pm', '18:45', 'at 7 in the evening'.

    Returns the next datetime at that clock time (today or tomorrow).
    """
    now = now or datetime.now()
    t = text.lower()
    t = re.sub(r"\bin the (morning)\b", "am", t)
    t = re.sub(r"\b(in the (evening|afternoon)|at night|tonight)\b", "pm", t)
    t = t.replace("noon", "12 pm").replace("midnight", "12 am")

    best = None
    for m in _CLOCK_RE.finditer(t):
        h = int(m.group("h"))
        mins = int(m.group("m") or 0)
        ampm = (m.group("ampm") or "").replace(".", "")
        # a bare number with no am/pm and no minutes is probably not a time
        # ("remind me in 5 minutes"), unless preceded by "at"
        if not ampm and m.group("m") is None:
            if not re.search(r"\b(at|for)\s+$", t[: m.start()]):
                continue
        if ampm == "pm" and h != 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
        if not (0 <= h <= 23 and 0 <= mins <= 59):
            continue
        best = (h, mins)
    if best is None:
        return None
    target = now.replace(hour=best[0], minute=best[1], second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


_CITY_RE = re.compile(
    r"\b(?:in|for|at|of|around)\s+([a-z][a-z .'-]*?)"
    r"(?:\s+(?:today|tomorrow|tonight|now|right now|this week|please))?\s*\??$"
)


def city(text: str) -> str | None:
    m = _CITY_RE.search(text.lower().strip())
    if not m:
        return None
    c = m.group(1).strip(" .")
    if c in {"the", "it", "there", "here", "outside", "the morning", "the evening"}:
        return None
    return c.title()


_REMIND_RE = re.compile(r"\bremind me (?:to|about|that)\s+(.+)", re.I)


def reminder_text(text: str) -> str | None:
    m = _REMIND_RE.search(text)
    if not m:
        return None
    body = m.group(1)
    # strip the time part: "call mom in 10 minutes" -> "call mom"
    body = re.split(r"\s+(?:in|after|at)\s+"
                    r"(?:\d|a\b|an\b|half|one|two|three|five|ten|fifteen|twenty|thirty)", body)[0]
    return body.strip(" .?!") or None


_DEF_RE = re.compile(
    r"^(?:.*?\b)?(?:wikipedia|define|definition of|meaning of|what does|who is|who was"
    r"|what is an?|what is the|what's an?|tell me about|look up|search wikipedia for)"
    r"\s+(.+?)(?:\s+mean)?(?:\s+on wikipedia)?\s*\??$"
)


def topic(text: str) -> str | None:
    t = text.lower().strip()
    t = re.sub(r"\s+(on|from|using) wikipedia$", "", t)
    m = _DEF_RE.search(t)
    if m:
        return m.group(1).strip(" .?") or None
    t = re.sub(r"\bwikipedia\b", "", t).strip()
    return t or None


_SEARCH_RE = re.compile(r"(?:search(?: the web| google| online)?(?: for)?|google|look up)\s+(.+)", re.I)


def search_query(text: str) -> str | None:
    m = _SEARCH_RE.search(text)
    return m.group(1).strip(" .?") if m else None


_PLAY_RE = re.compile(r"\bplay\s+(?:me\s+)?(?:some\s+)?(.+?)(?:\s+on\s+(?:youtube|spotify))?\s*$", re.I)


def song(text: str) -> str | None:
    m = _PLAY_RE.search(text)
    if not m:
        return None
    s = m.group(1).strip(" .")
    if s.lower() in {"music", "a song", "something", "songs"}:
        return None
    return s


_OPEN_RE = re.compile(r"\b(?:open|launch|go to|visit)\s+(?:up\s+)?(?:the\s+)?([\w.-]+)", re.I)


def website(text: str) -> str | None:
    m = _OPEN_RE.search(text)
    return m.group(1).lower() if m else None


def volume_direction(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\b(up|louder|increase|raise|higher|turn it up)\b", t):
        return "up"
    if re.search(r"\b(down|quieter|softer|decrease|lower|reduce)\b", t):
        return "down"
    if re.search(r"\b(mute|silence)\b", t):
        return "mute"
    return None


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def email_address(text: str) -> str | None:
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else None


def extract(intent: str, text: str, now: datetime | None = None) -> dict:
    """Run the extractors relevant to an intent."""
    out: dict = {}
    if intent == "weather":
        c = city(text)
        if c:
            out["city"] = c
    elif intent in ("reminder", "timer"):
        d = duration_seconds(text)
        if d:
            out["seconds"] = d
        else:
            at = clock_time(text, now)
            if at:
                out["at"] = at
        if intent == "reminder":
            r = reminder_text(text)
            if r:
                out["message"] = r
    elif intent == "alarm":
        at = clock_time(text, now)
        if at:
            out["at"] = at
    elif intent == "definition":
        tp = topic(text)
        if tp:
            out["topic"] = tp
    elif intent == "web_search":
        q = search_query(text)
        if q:
            out["query"] = q
    elif intent == "play_music":
        s = song(text)
        if s:
            out["song"] = s
    elif intent == "open_website":
        w = website(text)
        if w:
            out["site"] = w
    elif intent == "volume":
        v = volume_direction(text)
        if v:
            out["direction"] = v
    elif intent == "send_email":
        e = email_address(text)
        if e:
            out["to"] = e
    elif intent == "calculator":
        out["expression"] = text
    return out
