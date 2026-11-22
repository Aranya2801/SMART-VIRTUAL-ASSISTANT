"""TF-IDF + linear model intent classifier.

Word n-grams catch the phrasing, character n-grams make it a lot more
forgiving of the kind of spelling damage you get from speech recognition
("whether in delhi", "set a larm"). See experiments/ for how the two were
compared.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from .intents import OUT_OF_SCOPE


def build_features(char: bool = True, word: bool = True) -> FeatureUnion:
    parts = []
    if word:
        parts.append(("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)))
    if char:
        parts.append(("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5),
                                              sublinear_tf=True, min_df=2)))
    if not parts:
        raise ValueError("need at least one feature type")
    return FeatureUnion(parts)


def build_model(kind: str = "logreg", char: bool = True, word: bool = True, C: float = 10.0,
                balanced: bool = False) -> Pipeline:
    cw = "balanced" if balanced else None
    if kind == "logreg":
        clf = LogisticRegression(C=C, max_iter=2000, class_weight=cw)
    elif kind == "svm":
        # calibrated so we still get probabilities for the rejection threshold
        clf = CalibratedClassifierCV(LinearSVC(C=C / 10, class_weight=cw), cv=3)
    else:
        raise ValueError(f"unknown model kind {kind!r}")
    return Pipeline([("features", build_features(char, word)), ("clf", clf)])


@dataclass
class Prediction:
    intent: str
    confidence: float
    top: list[tuple[str, float]]


class IntentClassifier:
    def __init__(self, pipeline: Pipeline, threshold: float = 0.25):
        self.pipeline = pipeline
        self.threshold = threshold

    @classmethod
    def train(cls, texts, labels, threshold: float = 0.25, **kw) -> "IntentClassifier":
        pipe = build_model(**kw)
        pipe.fit(list(texts), list(labels))
        return cls(pipe, threshold)

    @property
    def classes(self) -> list[str]:
        return list(self.pipeline.classes_)

    def predict_proba(self, texts) -> np.ndarray:
        return self.pipeline.predict_proba(list(texts))

    def predict(self, texts, threshold: float | None = None) -> list[str]:
        thr = self.threshold if threshold is None else threshold
        probs = self.predict_proba(texts)
        classes = np.array(self.classes)
        best = probs.argmax(axis=1)
        labels = classes[best].astype(object)
        labels[probs.max(axis=1) < thr] = OUT_OF_SCOPE
        return [str(x) for x in labels]

    def predict_one(self, text: str, k: int = 3) -> Prediction:
        probs = self.predict_proba([text])[0]
        order = probs.argsort()[::-1][:k]
        top = [(str(self.classes[i]), float(probs[i])) for i in order]
        intent, conf = top[0]
        if conf < self.threshold or intent == OUT_OF_SCOPE:
            intent = OUT_OF_SCOPE
        return Prediction(intent, conf, top)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": self.pipeline, "threshold": self.threshold}, path)

    @classmethod
    def load(cls, path: str | Path) -> "IntentClassifier":
        obj = joblib.load(path)
        return cls(obj["pipeline"], obj["threshold"])
