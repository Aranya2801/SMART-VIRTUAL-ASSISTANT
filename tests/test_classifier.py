from aria.nlu.classifier import IntentClassifier
from aria.nlu.intents import OUT_OF_SCOPE

DATA = [
    ("what's the weather", "weather"), ("is it raining", "weather"), ("weather today", "weather"),
    ("how hot is it", "weather"), ("will it rain tomorrow", "weather"),
    ("set a timer for 5 minutes", "timer"), ("timer 10 minutes", "timer"),
    ("start a timer", "timer"), ("countdown 3 minutes", "timer"), ("i need a timer", "timer"),
    ("transfer money to savings", OUT_OF_SCOPE), ("book a flight", OUT_OF_SCOPE),
    ("order a pizza", OUT_OF_SCOPE), ("what's my credit score", OUT_OF_SCOPE),
    ("find a hotel", OUT_OF_SCOPE),
]


def test_train_predict_roundtrip(tmp_path):
    texts, labels = zip(*DATA)
    m = IntentClassifier.train(texts, labels, threshold=0.0, char=True, word=True)
    assert m.predict_one("whats the wether like").intent == "weather"  # typo on purpose
    assert m.predict_one("set timer for two minutes").intent == "timer"
    p = tmp_path / "m.joblib"
    m.save(p)
    m2 = IntentClassifier.load(p)
    assert m2.predict(["weather today"]) == ["weather"]


def test_threshold_rejects_low_confidence():
    texts, labels = zip(*DATA)
    m = IntentClassifier.train(texts, labels)
    assert m.predict(["weather today"], threshold=0.99) == [OUT_OF_SCOPE]
