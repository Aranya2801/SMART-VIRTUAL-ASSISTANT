"""End-to-end dialogue tests with no network, browser or audio."""

import threading
from datetime import datetime

import pytest

from aria.assistant import Assistant
from aria.config import Settings
from aria.nlu import NLU
from aria.speech import ConsoleSpeaker


class FakeResponse:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data


class FakeHTTP:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, **kw):
        self.calls.append((url, kw))
        for prefix, resp in self.routes.items():
            if url.startswith(prefix):
                return resp
        raise AssertionError(f"unexpected url {url}")


@pytest.fixture
def bot():
    opened = []
    http = FakeHTTP({
        "https://api.openweathermap.org": FakeResponse({
            "cod": 200, "name": "Pune", "weather": [{"description": "light rain"}],
            "main": {"temp": 24.4, "feels_like": 24.9, "humidity": 81}}),
    })
    s = Settings(weather_api_key="test", model_path="does-not-exist")
    b = Assistant(s, ConsoleSpeaker(), nlu=NLU(None), http=http, open_url=opened.append,
                  now=lambda: datetime(2026, 1, 10, 9, 0))
    b.opened, b.http = opened, http
    yield b
    b.close()


def last(bot):
    return bot.speaker.history[-1]


def test_weather_uses_city_slot(bot):
    bot.handle("weather in pune")
    assert last(bot) == "In Pune it's 24 degrees with light rain. Humidity is 81 percent."
    assert bot.http.calls[0][1]["params"]["q"] == "Pune"


def test_alarm_asks_for_missing_time_then_sets_it(bot):
    assert bot.handle("set an alarm") == "What time should I set the alarm for?"
    reply = bot.handle("6 30 am")
    assert reply.startswith("Alarm set for 6:30 AM")
    assert [j.kind for j in bot.scheduler.pending()] == ["alarm"]


def test_reminder_fills_both_slots_over_two_turns(bot):
    assert bot.handle("remind me to") == "What should I remind you about?"
    assert bot.handle("water the plants").startswith("When?")
    assert bot.handle("in 20 minutes") == "Okay, I'll remind you to water the plants in 20 minutes."


def test_reminder_actually_fires(bot):
    fired = threading.Event()
    orig = bot.speaker.say

    def say(text):
        orig(text)
        if text.startswith("Reminder:"):
            fired.set()
    bot.ctx.say = say
    bot._run("reminder", {"message": "stretch", "seconds": 0.05})
    assert fired.wait(2)
    assert "Reminder: stretch." in bot.speaker.history


def test_cancel_mid_dialogue(bot):
    bot.handle("set an alarm")
    assert bot.handle("never mind") == "Okay, never mind."
    assert bot.pending is None


def test_out_of_scope_asks_before_searching(bot):
    reply = bot.handle("book me a cab to the airport")
    assert "search the web" in reply
    assert bot.opened == []
    bot.handle("yes")
    assert bot.opened and "book+me+a+cab" in bot.opened[0]


def test_out_of_scope_declined(bot):
    bot.handle("book me a cab")
    assert bot.handle("no") == "No problem."
    assert bot.opened == []


def test_calculator_is_safe(bot):
    assert bot.handle("what is 6 times 7") == "That's 42."
    assert "couldn't" in bot.handle("what is __import__('os').getcwd()")


def test_list_and_cancel_alarms(bot):
    bot.handle("set an alarm for 7 am")
    assert "alarm '7:00 AM'" in bot.handle("what alarms do i have")
    assert bot.handle("cancel all alarms") == "Cancelled 1 alarm."
    assert bot.handle("what alarms do i have") == "You don't have any reminders or alarms."


def test_goodbye_stops_loop(bot):
    bot.handle("goodbye")
    assert bot.running is False


def test_open_unknown_site_does_not_guess_domain(bot):
    bot.handle("open someobscurething")
    assert bot.opened[0].startswith("https://duckduckgo.com/")


def test_gives_up_on_follow_up_after_two_bad_answers(bot):
    bot.handle("set an alarm")
    assert bot.handle("hmm") == "I didn't get the time. Try '7:30 am'."
    # second miss: treat it as a new request instead of asking forever
    assert bot.handle("what is 2 plus 2") == "That's 4."
    assert bot.pending is None


def test_never_mind_with_nothing_pending(bot):
    assert bot.handle("never mind") == "Okay."


def test_wikipedia_summary_is_trimmed(bot):
    bot.http.routes = {"https://en.wikipedia.org/api/rest_v1/page/summary/": FakeResponse({
        "type": "standard",
        "extract": "Ada Lovelace was a mathematician. She wrote the first program. She died in 1852."})}
    assert bot.handle("wikipedia ada lovelace") == \
        "Ada Lovelace was a mathematician. She wrote the first program."
    assert bot.http.calls[-1][0].endswith("/ada_lovelace")
