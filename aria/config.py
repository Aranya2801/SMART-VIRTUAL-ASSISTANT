"""Settings loading.

Order of precedence: environment variables > config file > defaults.
Secrets (API keys, email password) should live in env vars or in a
config.json that is git-ignored.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, fields
from pathlib import Path

DEFAULT_CONFIG_PATHS = (
    Path("config.json"),
    Path("config") / "config.json",
    Path.home() / ".config" / "aria" / "config.json",
)


@dataclass
class Settings:
    mode: str = "text"  # "text" or "voice"
    language: str = "en-IN"
    default_city: str = "Kolkata"
    news_country: str = "in"

    weather_api_key: str = ""
    news_api_key: str = ""
    email: str = ""
    email_password: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587

    voice_rate: int = 170
    voice_volume: float = 0.95
    voice_index: int = 0

    model_path: str = "models/intent_clf.joblib"
    # below this probability the assistant treats the request as unsupported
    confidence_threshold: float | None = None  # None = use the value saved with the model
    # if no trained model is found, fall back to the keyword router
    allow_rule_fallback: bool = True


# old config files used upper-case keys, keep reading them
_LEGACY_KEYS = {
    "WEATHER_API_KEY": "weather_api_key",
    "NEWS_API_KEY": "news_api_key",
    "EMAIL": "email",
    "EMAIL_PASSWORD": "email_password",
}


def load_settings(path: str | os.PathLike | None = None) -> Settings:
    raw: dict = {}
    candidates = [Path(path)] if path else list(DEFAULT_CONFIG_PATHS)
    for p in candidates:
        if p.is_file():
            with open(p, encoding="utf-8") as fh:
                raw = json.load(fh)
            break
        if path:  # explicit path that doesn't exist is an error
            raise FileNotFoundError(p)

    for old, new in _LEGACY_KEYS.items():
        if old in raw and new not in raw:
            raw[new] = raw.pop(old)

    s = Settings()
    known = {f.name: f.type for f in fields(Settings)}
    for key, value in raw.items():
        if key in known:
            setattr(s, key, value)

    # env vars win, e.g. ARIA_WEATHER_API_KEY
    for name in known:
        env = os.environ.get(f"ARIA_{name.upper()}")
        if env is None:
            continue
        current = getattr(s, name)
        if isinstance(current, bool):
            setattr(s, name, env.strip().lower() in {"1", "true", "yes"})
        elif isinstance(current, int):
            setattr(s, name, int(env))
        elif isinstance(current, float):
            setattr(s, name, float(env))
        else:
            setattr(s, name, env)
    return s
