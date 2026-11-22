from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from . import rules, slots
from .intents import OUT_OF_SCOPE

log = logging.getLogger(__name__)


@dataclass
class Parse:
    text: str
    intent: str
    confidence: float
    slots: dict = field(default_factory=dict)
    alternatives: list = field(default_factory=list)
    source: str = "model"  # "model" or "rules"


class NLU:
    """Intent + slots. Uses the trained model if there is one, otherwise rules."""

    def __init__(self, model_path: str | Path | None = None, threshold: float | None = None,
                 allow_rule_fallback: bool = True):
        self.model = None
        if model_path and Path(model_path).is_file():
            from .classifier import IntentClassifier
            self.model = IntentClassifier.load(model_path)
            if threshold is not None:
                self.model.threshold = threshold
            log.info("loaded intent model from %s", model_path)
        elif not allow_rule_fallback:
            raise FileNotFoundError(f"no intent model at {model_path}; run `python -m aria.train`")
        else:
            log.warning("no intent model found, using keyword rules (run `python -m aria.train`)")

    def parse(self, text: str) -> Parse:
        text = text.strip()
        if self.model is not None:
            p = self.model.predict_one(text)
            intent, conf, alts, src = p.intent, p.confidence, p.top, "model"
        else:
            intent = rules.classify(text)
            conf = 1.0 if intent != OUT_OF_SCOPE else 0.0
            alts, src = [], "rules"
        extracted = slots.extract(intent, text) if intent != OUT_OF_SCOPE else {}
        return Parse(text, intent, conf, extracted, alts, src)
