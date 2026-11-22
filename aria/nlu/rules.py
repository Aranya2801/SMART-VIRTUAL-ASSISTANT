"""Keyword router.

This is the routing logic from the original (v1/v2) assistant, pulled out of
the big if/elif chain so it returns an intent label instead of acting on it.
I kept the keyword lists and the order of checks the same so it can be used
as a fair baseline in experiments/run_benchmark.py. Two things were changed
compared to the old script:

  * keywords can match on word boundaries, so "stop" no longer fires on
    "bus stops" (and quits the app) and "news" no longer fires on
    "newsletter". The old plain substring behaviour is still available
    (word_boundary=False) and the benchmark reports both.
  * the final "google it" fallback becomes OUT_OF_SCOPE.
"""

from __future__ import annotations

import re

from .intents import OUT_OF_SCOPE

# (intent, keywords) in the same priority order as the old route_command()
RULES: list[tuple[str, list[str]]] = [
    ("definition", ["wikipedia"]),
    ("time", ["what time", "current time", "time now"]),
    ("date", ["what date", "today's date", "current date"]),
    ("weather", ["weather"]),
    ("news", ["news"]),
    ("joke", ["joke", "funny", "make me laugh"]),
    ("motivation", ["motivate", "inspire", "motivation", "inspiration"]),
    ("fun_fact", ["fact", "interesting", "did you know"]),
    ("open_website", ["open"]),
    ("web_search", ["search", "google"]),
    ("play_music", ["play youtube"]),  # old code required both words, handled below
    ("reminder", ["remind me"]),
    ("alarm", ["set alarm", "set an alarm"]),
    ("send_email", ["send email", "compose email"]),
    ("volume", ["volume up", "volume down"]),
    ("screenshot", ["screenshot"]),
    ("calculator", ["calculate", "what is"]),
    ("help", ["who are you", "what can you do", "help"]),
    ("goodbye", ["stop", "exit", "quit", "goodbye", "bye"]),
]


def _contains(text: str, kw: str, word_boundary: bool) -> bool:
    if not word_boundary:
        return kw in text
    return re.search(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", text) is not None


def classify(text: str, word_boundary: bool = True) -> str:
    q = text.lower().strip()
    if not q:
        return OUT_OF_SCOPE
    for intent, keywords in RULES:
        if intent == "play_music":
            if _contains(q, "play", word_boundary) and _contains(q, "youtube", word_boundary):
                return intent
            continue
        if any(_contains(q, k, word_boundary) for k in keywords):
            return intent
    return OUT_OF_SCOPE
