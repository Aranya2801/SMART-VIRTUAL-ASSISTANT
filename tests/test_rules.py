from aria.nlu import rules
from aria.nlu.intents import OUT_OF_SCOPE


def test_original_keywords_still_route():
    assert rules.classify("wikipedia python") == "definition"
    assert rules.classify("what time is it") == "time"
    assert rules.classify("weather in mumbai") == "weather"
    assert rules.classify("play despacito on youtube") == "play_music"


def test_word_boundary_fixes_substring_bugs():
    # "stops" contains "stop", "newsletter" contains "news"
    assert rules.classify("show me nearby bus stops", word_boundary=False) == "goodbye"
    assert rules.classify("show me nearby bus stops", word_boundary=True) == OUT_OF_SCOPE
    assert rules.classify("unsubscribe from the newsletter", word_boundary=False) == "news"
    assert rules.classify("unsubscribe from the newsletter") == OUT_OF_SCOPE


def test_unknown_is_out_of_scope():
    assert rules.classify("book a cab to the airport") == OUT_OF_SCOPE
    assert rules.classify("") == OUT_OF_SCOPE
