"""Dialogue loop: text in, spoken/printed replies out.

The old script asked follow-up questions with input(), which meant voice
mode suddenly needed a keyboard for reminders, alarms and email. Here a
missing slot is remembered as "pending" and the next thing the user says is
used to fill it, whether it came from the mic or the keyboard.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import quote_plus

from . import skills
from .config import Settings
from .nlu import NLU, OUT_OF_SCOPE
from .nlu import slots as slotlib
from .scheduler import Scheduler

log = logging.getLogger(__name__)

YES = re.compile(r"^(yes|yeah|yep|yup|sure|ok(ay)?|do it|go ahead|please do|send it|correct)\b", re.I)
NO = re.compile(r"^(no|nope|nah|cancel|don'?t|stop|never ?mind)\b", re.I)
NEVERMIND = re.compile(r"^(never ?mind|forget it|cancel( that)?)[.!]?$", re.I)
CANCEL = re.compile(r"^(cancel|never ?mind|forget it|stop)\b", re.I)
LIST_JOBS = re.compile(r"\b(what|which|list|show)\b.*\b(reminders?|alarms?|timers?)\b", re.I)
CANCEL_JOBS = re.compile(r"\b(cancel|delete|remove|clear)\b.*\b(all )?(reminders?|alarms?|timers?)\b", re.I)


@dataclass
class Pending:
    intent: str
    slots: dict
    waiting_for: str
    retries: int = 0


class Assistant:
    def __init__(self, settings: Settings, speaker, nlu: NLU | None = None,
                 scheduler: Scheduler | None = None, **ctx_overrides):
        self.settings = settings
        self.speaker = speaker
        self.nlu = nlu or NLU(settings.model_path, settings.confidence_threshold,
                              settings.allow_rule_fallback)
        self.scheduler = scheduler or Scheduler()
        self.ctx = skills.Context(settings=settings, say=speaker.say,
                                  scheduler=self.scheduler, **ctx_overrides)
        self.pending: Pending | None = None
        self.confirm: skills.Confirm | None = None
        self.running = True

    # ------------------------------------------------------------------
    def handle(self, text: str) -> str | None:
        text = (text or "").strip()
        if not text:
            return None

        if self.confirm is not None:
            c, self.confirm = self.confirm, None
            if YES.search(text):
                return self._say(c.on_yes())
            if NO.search(text):
                return self._say(c.on_no)
            # anything else: drop the confirmation and treat it as a new request

        if CANCEL.search(text) and len(text.split()) <= 3:
            if self.pending is not None:
                self.pending = None
                return self._say("Okay, never mind.")
            if NEVERMIND.match(text):
                return self._say("Okay.")

        if self.pending is not None:
            return self._fill_pending(text)

        if LIST_JOBS.search(text):
            return self._say(skills.list_jobs(self.ctx, {}))
        m = CANCEL_JOBS.search(text)
        if m:
            kind = m.group(3).rstrip("s")
            n = self.scheduler.cancel(kind=kind)
            return self._say(f"Cancelled {n} {kind}{'s' if n != 1 else ''}." if n
                             else f"You don't have any {kind}s set.")

        parse = self.nlu.parse(text)
        log.debug("parse: %s", parse)
        if parse.intent == OUT_OF_SCOPE:
            return self._out_of_scope(text)
        return self._run(parse.intent, parse.slots)

    # ------------------------------------------------------------------
    def _run(self, intent: str, slots: dict) -> str | None:
        handler = skills.HANDLERS.get(intent)
        if handler is None:
            return self._say("I know what you mean but I can't do that yet.")
        result = handler(self.ctx, slots)
        if isinstance(result, skills.Ask):
            self.pending = Pending(intent, slots, result.slot)
            return self._say(result.prompt)
        if isinstance(result, skills.Confirm):
            self.confirm = result
            return self._say(result.prompt)
        if intent == "goodbye":
            self.running = False
        return self._say(result)

    def _retry(self, p: Pending, text: str, prompt: str) -> str | None:
        # ask again once; if the second answer doesn't fit either, assume the
        # user has moved on and treat it as a fresh request
        if p.retries >= 1:
            return self.handle(text)
        p.retries += 1
        self.pending = p
        return self._say(prompt)

    def _fill_pending(self, text: str) -> str | None:
        p, self.pending = self.pending, None
        slot = p.waiting_for
        if slot in ("seconds", "when"):
            secs = slotlib.duration_seconds(text)
            at = None if secs else slotlib.clock_time("at " + text if text[0].isdigit() else text)
            if secs:
                p.slots["seconds"] = secs
            elif at:
                p.slots["at"] = at
            else:
                return self._retry(p, text, "Sorry, I didn't catch a time. Something like 'in 10 minutes'?")
        elif slot == "at":
            at = slotlib.clock_time(text if not text[0].isdigit() else "at " + text)
            if not at:
                return self._retry(p, text, "I didn't get the time. Try '7:30 am'.")
            p.slots["at"] = at
        elif slot == "to":
            addr = slotlib.email_address(text.replace(" at ", "@").replace(" dot ", "."))
            if not addr:
                return self._retry(p, text, "That doesn't look like an email address.")
            p.slots["to"] = addr
        elif slot == "direction":
            d = slotlib.volume_direction(text)
            if not d:
                return self._retry(p, text, "Up, down or mute?")
            p.slots["direction"] = d
        elif slot == "site":
            p.slots["site"] = slotlib.website("open " + text) or text
        else:
            p.slots[slot] = text.strip(" .?")
        return self._run(p.intent, p.slots)

    def _out_of_scope(self, text: str) -> str | None:
        query = text

        def _search():
            self.ctx.open_url("https://www.google.com/search?q=" + quote_plus(query))
            return "Opened a web search."

        self.confirm = skills.Confirm("I can't help with that one myself. Want me to search the web for it?",
                                      _search, on_no="No problem.")
        return self._say(self.confirm.prompt)

    def _say(self, text: str) -> str:
        self.speaker.say(text)
        return text

    def close(self) -> None:
        self.scheduler.stop()
        self.speaker.close()
