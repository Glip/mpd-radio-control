from pathlib import Path

import pytest

from app.config import get_settings, load_settings_from_file, resolve_config_path


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _write_config(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_load_yaml_config(tmp_path):
    cfg = _write_config(
        tmp_path / "config.yaml",
        """
server:
  host: 127.0.0.1
  port: 9090
  max_upload_mb: 100
instances:
  - id: rock
    host: mpd-rock
    port: 6600
    music_dir: /music/rock
    label: Rock Radio
  - id: jazz
    host: 127.0.0.1
    port: 6602
    music_dir: /music/jazz
""",
    )
    settings = load_settings_from_file(cfg)
    assert settings.host == "127.0.0.1"
    assert settings.port == 9090
    assert settings.max_upload_mb == 100
    assert len(settings.instances) == 2
    assert settings.instances[0].label == "Rock Radio"
    assert settings.instances[1].host == "127.0.0.1"
    assert settings.instances[1].label == "jazz"


def test_resolve_config_from_env(monkeypatch, tmp_path):
    cfg = _write_config(
        tmp_path / "desk.yaml",
        """
instances:
  - id: chill
    host: mpd
    port: 6600
    music_dir: /music/chill
    label: Chill
""",
    )
    monkeypatch.setenv("RADIO_DESK_CONFIG", str(cfg))
    assert resolve_config_path() == cfg.resolve()
    settings = get_settings()
    assert settings.instances[0].id == "chill"


def test_missing_instances_raises(tmp_path):
    cfg = _write_config(tmp_path / "bad.yaml", "server:\n  port: 8080\n")
    with pytest.raises(ValueError, match="instances"):
        load_settings_from_file(cfg)


def test_duplicate_ids_raise(tmp_path):
    cfg = _write_config(
        tmp_path / "dup.yaml",
        """
instances:
  - id: rock
    host: a
    port: 6600
  - id: rock
    host: b
    port: 6601
""",
    )
    with pytest.raises(ValueError, match="unique"):
        load_settings_from_file(cfg)


def test_repo_default_config_loads():
    repo_cfg = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
    settings = load_settings_from_file(repo_cfg)
    assert len(settings.instances) >= 1
    assert settings.port == 8080
