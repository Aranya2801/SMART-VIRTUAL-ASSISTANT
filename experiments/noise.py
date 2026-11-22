"""Synthetic ASR-style corruption of transcripts.

This is NOT a real speech recogniser. It's a cheap stand-in for the usual
ASR error types: words swapped for something that sounds similar, short words
dropped, words glued together or split, and the odd mangled spelling. Good
enough to compare how fragile different intent models are relative to each
other. The absolute numbers say nothing about real audio; evaluating on
actual recordings is listed as future work.
"""

from __future__ import annotations

import random
import re

# hand-picked sound-alike swaps for words that matter to ARIA's intents
HOMOPHONES = {
    "weather": ["whether", "wetter"], "whether": ["weather"],
    "alarm": ["a larm", "alarms", "balm"], "timer": ["timor", "time are"],
    "set": ["sit", "said"], "for": ["four", "far"], "to": ["two", "too"],
    "two": ["to"], "four": ["for"], "eight": ["ate"], "one": ["won"],
    "remind": ["re mind", "remained"], "me": ["mi"], "joke": ["choke", "yoke"],
    "time": ["thyme", "tie"], "date": ["data", "day"], "what": ["what's", "wat"],
    "what's": ["what", "watts"], "volume": ["value", "volumes"], "music": ["muse"],
    "play": ["pray", "plate"], "tell": ["tall", "till"], "fact": ["fat", "facts"],
    "hi": ["high"], "bye": ["by", "buy"], "goodbye": ["good bye"],
    "calculate": ["calculator", "calculated"], "plus": ["plush"], "times": ["time"],
    "the": ["a", "de"], "is": ["his", "as"], "you": ["u", "ya"], "your": ["you're"],
    "minutes": ["minute", "mints"], "hour": ["our", "are"], "tomorrow": ["to morrow"],
    "meaning": ["morning"], "define": ["divine"], "up": ["app"], "down": ["town"],
}

_CHAR_RULES = [
    (r"th", "d"), (r"v", "w"), (r"w", "v"), (r"ee", "i"), (r"ph", "f"),
    (r"(.)\1", r"\1"), (r"s$", ""), (r"ed$", ""), (r"z", "s"), (r"ck", "k"),
]


def _phonetic(word: str, rng: random.Random) -> str:
    if word in HOMOPHONES and rng.random() < 0.7:
        return rng.choice(HOMOPHONES[word])
    rules = [r for r in _CHAR_RULES if re.search(r[0], word)]
    if rules:
        pat, rep = rng.choice(rules)
        return re.sub(pat, rep, word, count=1)
    return _typo(word, rng)


def _typo(word: str, rng: random.Random) -> str:
    if len(word) < 3:
        return word
    i = rng.randrange(1, len(word))
    op = rng.random()
    if op < 0.5:
        return word[:i] + rng.choice("aeiou") + word[i + 1:]
    return word[:i] + word[i + 1:]


def corrupt(text: str, p: float, rng: random.Random) -> str:
    """Corrupt each word with probability p."""
    if p <= 0:
        return text
    words = text.split()
    out: list[str] = []
    i = 0
    while i < len(words):
        w = words[i]
        if rng.random() >= p:
            out.append(w)
            i += 1
            continue
        r = rng.random()
        if r < 0.45:
            out.append(_phonetic(w, rng))
        elif r < 0.70:
            # deletions mostly hit short function words
            if len(w) > 4 and rng.random() < 0.6:
                out.append(_phonetic(w, rng))
        elif r < 0.85 and i + 1 < len(words):
            out.append(w + words[i + 1])  # "set a" -> "seta"
            i += 1
        elif r < 0.90 and len(w) > 5:
            k = rng.randrange(2, len(w) - 2)
            out.extend([w[:k], w[k:]])
        else:
            out.append(_typo(w, rng))
        i += 1
    return " ".join(out) if out else text


def corrupt_all(texts, p: float, seed: int = 0) -> list[str]:
    rng = random.Random(seed)
    return [corrupt(t, p, rng) for t in texts]
