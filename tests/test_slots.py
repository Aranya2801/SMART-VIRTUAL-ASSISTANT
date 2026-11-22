from datetime import datetime

import pytest

from aria.nlu import slots

NOW = datetime(2026, 1, 10, 14, 0)


@pytest.mark.parametrize("text,secs", [
    ("set a timer for 5 minutes", 300),
    ("remind me in 1 hour and 20 minutes", 4800),
    ("ten seconds", 10),
    ("in half an hour", 1800),
    ("for an hour", 3600),
    ("set a timer", None),
])
def test_duration(text, secs):
    assert slots.duration_seconds(text) == secs


@pytest.mark.parametrize("text,hm,day", [
    ("wake me up at 7:30 am", (7, 30), 11),
    ("set an alarm for 6 pm", (18, 0), 10),
    ("alarm at 18:45", (18, 45), 10),
    ("at 9 in the morning", (9, 0), 11),
    ("set alarm for 7 30 am", (7, 30), 11),
    ("at noon", (12, 0), 11),
])
def test_clock_time(text, hm, day):
    t = slots.clock_time(text, NOW)
    assert (t.hour, t.minute) == hm
    assert t.day == day


def test_bare_number_is_not_a_time():
    assert slots.clock_time("remind me in 5 minutes", NOW) is None


@pytest.mark.parametrize("text,city", [
    ("what's the weather in new delhi", "New Delhi"),
    ("weather for bhubaneswar tomorrow", "Bhubaneswar"),
    ("is it going to rain", None),
    ("how hot is it outside", None),
])
def test_city(text, city):
    assert slots.city(text) == city


def test_reminder_text():
    assert slots.reminder_text("remind me to call mom in 10 minutes") == "call mom"
    assert slots.reminder_text("remind me to submit the report at 5 pm") == "submit the report"
    assert slots.reminder_text("set a reminder") is None


@pytest.mark.parametrize("text,topic", [
    ("who is alan turing", "alan turing"),
    ("wikipedia black holes", "black holes"),
    ("what does serendipity mean", "serendipity"),
    ("tell me about the taj mahal", "the taj mahal"),
])
def test_topic(text, topic):
    assert slots.topic(text) == topic


def test_misc_extractors():
    assert slots.email_address("send it to a.b+c@example.co.in please") == "a.b+c@example.co.in"
    assert slots.volume_direction("make it louder") == "up"
    assert slots.website("open github") == "github"
    assert slots.song("play believer on youtube") == "believer"
    assert slots.song("play some music") is None
    assert slots.search_query("search for gate syllabus") == "gate syllabus"
