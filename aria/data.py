"""Training data: CLINC150 mapped onto ARIA's intents, plus data/aria_extra.tsv.

CLINC150 (Larson et al., 2019) has 150 intents across 10 domains plus a set
of out-of-scope queries. ARIA only supports a few of those intents, so every
other CLINC intent is something ARIA should *refuse* rather than misroute.
That makes it a decent test bed for open-set intent detection on a small
assistant, which is what experiments/ looks at.

The dataset is CC BY 3.0 and is downloaded on first use, not committed.
"""

from __future__ import annotations

import json
import random
import urllib.request
from collections import Counter
from pathlib import Path

from .nlu.intents import OUT_OF_SCOPE

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CLINC_URL = "https://raw.githubusercontent.com/clinc/oos-eval/master/data/data_full.json"
CLINC_PATH = DATA_DIR / "clinc150" / "data_full.json"
EXTRA_PATH = DATA_DIR / "aria_extra.tsv"

CLINC_TO_ARIA = {
    "weather": "weather",
    "time": "time",
    "date": "date",
    "alarm": "alarm",
    # careful: in CLINC "reminder" means *reading* your reminders and
    # "reminder_update" is the one that creates them
    "reminder_update": "reminder",
    "reminder": "list_reminders",
    "timer": "timer",
    "calculator": "calculator",
    "tell_joke": "joke",
    "fun_fact": "fun_fact",
    "play_music": "play_music",
    "change_volume": "volume",
    "definition": "definition",
    "greeting": "greeting",
    "goodbye": "goodbye",
    "what_can_i_ask_you": "help",
    "what_is_your_name": "about",
    "who_made_you": "about",
    "are_you_a_bot": "about",
}


def load_clinc(path: Path = CLINC_PATH, download: bool = True) -> dict:
    if not path.is_file():
        if not download:
            raise FileNotFoundError(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading CLINC150 -> {path}")
        urllib.request.urlretrieve(CLINC_URL, path)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_extra(path: Path = EXTRA_PATH) -> list[tuple[str, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        intent, text = line.split("\t", 1)
        rows.append((text.strip(), intent.strip()))
    return rows


def unsupported_split(clinc: dict, seed: int = 0) -> tuple[set[str], set[str]]:
    """Split CLINC intents ARIA doesn't support into two disjoint halves.

    'seen' ones are used as negative training examples (an explicit oos
    class), 'unseen' ones only ever show up at test time. This is to check
    whether a reject class learned from some unsupported requests carries
    over to different ones.
    """
    all_intents = sorted({lbl for _, lbl in clinc["train"]})
    unsupported = [i for i in all_intents if i not in CLINC_TO_ARIA]
    rng = random.Random(seed)
    rng.shuffle(unsupported)
    half = len(unsupported) // 2
    return set(unsupported[:half]), set(unsupported[half:])


def build_split(clinc: dict, split: str, seen_unsupported: set[str] | None = None,
                per_intent: int | None = None, seed: int = 0):
    """Return (texts, aria_labels, groups) for a CLINC split.

    groups tells you where each example came from:
      'in'      - one of ARIA's intents
      'u_seen'  - unsupported CLINC intent from the seen half
      'u_unseen'- unsupported CLINC intent from the unseen half
      'oos'     - CLINC's own out-of-scope queries
    """
    seen_unsupported = seen_unsupported or set()
    rng = random.Random(seed)
    rows = list(clinc[split])
    if per_intent is not None:
        rng.shuffle(rows)
        counts: Counter = Counter()
        kept = []
        for text, lbl in rows:
            if counts[lbl] < per_intent:
                kept.append((text, lbl))
                counts[lbl] += 1
        rows = kept

    texts, labels, groups = [], [], []
    for text, lbl in rows:
        if lbl in CLINC_TO_ARIA:
            labels.append(CLINC_TO_ARIA[lbl])
            groups.append("in")
        else:
            labels.append(OUT_OF_SCOPE)
            groups.append("u_seen" if lbl in seen_unsupported else "u_unseen")
        texts.append(text)

    oos_key = {"train": "oos_train", "val": "oos_val", "test": "oos_test"}[split]
    for text, _ in clinc[oos_key]:
        texts.append(text)
        labels.append(OUT_OF_SCOPE)
        groups.append("oos")
    return texts, labels, groups


def training_set(clinc: dict, include_extra: bool = True, seed: int = 0):
    """Everything the shipped model is trained on.

    In-scope CLINC examples, the seen half of unsupported intents + CLINC oos
    as the reject class, and the hand-written extra intents.
    """
    seen, _ = unsupported_split(clinc, seed)
    texts, labels, groups = build_split(clinc, "train", seen)
    keep = [g in ("in", "u_seen", "oos") for g in groups]
    texts = [t for t, k in zip(texts, keep) if k]
    labels = [lbl for lbl, k in zip(labels, keep) if k]
    if include_extra:
        for t, lbl in load_extra():
            texts.append(t)
            labels.append(lbl)
    return texts, labels
