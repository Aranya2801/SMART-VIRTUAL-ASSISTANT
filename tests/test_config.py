import json

from aria.config import load_settings


def test_legacy_keys_and_env_override(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"WEATHER_API_KEY": "abc", "default_city": "Pune", "voice_rate": 150}))
    monkeypatch.setenv("ARIA_DEFAULT_CITY", "Kolkata")
    monkeypatch.setenv("ARIA_VOICE_RATE", "190")
    s = load_settings(cfg)
    assert s.weather_api_key == "abc"
    assert s.default_city == "Kolkata"
    assert s.voice_rate == 190


def test_defaults_without_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    s = load_settings()
    assert s.mode == "text"
    assert s.weather_api_key == ""
