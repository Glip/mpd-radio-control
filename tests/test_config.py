import os

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_parse_csv_instances(monkeypatch):
    monkeypatch.setenv(
        "MPD_INSTANCES",
        "rock:mpd-rock:6600:/music/rock:Rock Radio,jazz:127.0.0.1:6602:/music/jazz",
    )
    monkeypatch.delenv("MPD_INSTANCES_JSON", raising=False)
    settings = get_settings()
    assert len(settings.instances) == 2
    assert settings.instances[0].id == "rock"
    assert settings.instances[0].label == "Rock Radio"
    assert settings.instances[1].host == "127.0.0.1"
    assert settings.instances[1].port == 6602
    assert settings.instances[1].label == "jazz"


def test_parse_json_instances(monkeypatch):
    monkeypatch.setenv(
        "MPD_INSTANCES_JSON",
        '[{"id":"chill","host":"mpd","port":6600,"music_dir":"/music/chill","label":"Chill"}]',
    )
    settings = get_settings()
    assert len(settings.instances) == 1
    assert settings.instances[0].id == "chill"
    assert settings.instances[0].label == "Chill"


def test_invalid_csv_raises(monkeypatch):
    monkeypatch.setenv("MPD_INSTANCES", "broken-entry")
    monkeypatch.delenv("MPD_INSTANCES_JSON", raising=False)
    with pytest.raises(ValueError):
        get_settings()
