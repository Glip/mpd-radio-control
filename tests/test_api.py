from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import MpdInstance, get_settings
from app.main import app


@pytest.fixture(autouse=True)
def configure_env(monkeypatch, tmp_path):
    get_settings.cache_clear()
    music = tmp_path / "music"
    music.mkdir()
    monkeypatch.setenv(
        "MPD_INSTANCES",
        f"rock:127.0.0.1:6601:{music}:Rock Radio",
    )
    monkeypatch.delenv("MPD_INSTANCES_JSON", raising=False)
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_index_renders(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Radio Desk" in res.text
    assert "Rock Radio" in res.text


def test_play_endpoint(client):
    fake_status = {
        "id": "rock",
        "label": "Rock Radio",
        "online": True,
        "state": "play",
        "current": {"title": "Song", "file": "a.mp3"},
    }
    with patch("app.routers.api.mpd_client.play", new=AsyncMock(return_value=fake_status)):
        res = client.post("/api/instances/rock/play", json={})
    assert res.status_code == 200
    assert res.json()["state"] == "play"


def test_unknown_instance(client):
    res = client.post("/api/instances/nope/stop")
    assert res.status_code == 404


def test_upload_track(client, tmp_path):
    settings = get_settings()
    instance = settings.instances[0]
    assert Path(instance.music_dir).exists()

    fake_status = {
        "id": "rock",
        "label": "Rock Radio",
        "online": True,
        "state": "play",
        "current": {"title": "demo", "file": "demo.mp3"},
    }

    with (
        patch("app.uploads.mpd_client.update_db", new=AsyncMock(return_value={"updating_db": "1"})),
        patch("app.uploads.mpd_client.add_to_playlist", new=AsyncMock(return_value=fake_status)),
    ):
        res = client.post(
            "/api/instances/rock/upload/track",
            data={"play_now": "true"},
            files={"file": ("demo.mp3", b"ID3fakeaudio", "audio/mpeg")},
        )

    assert res.status_code == 200
    body = res.json()
    assert body["file"] == "demo.mp3"
    assert (Path(instance.music_dir) / "demo.mp3").exists()


def test_upload_album_files(client):
    settings = get_settings()
    instance = settings.instances[0]
    fake_status = {"id": "rock", "online": True, "state": "stop", "current": None}

    with (
        patch("app.uploads.mpd_client.update_db", new=AsyncMock(return_value={"updating_db": "1"})),
        patch("app.uploads.mpd_client.run_mpd", new=AsyncMock(return_value=None)),
        patch("app.uploads.mpd_client.get_status", new=AsyncMock(return_value=fake_status)),
    ):
        res = client.post(
            "/api/instances/rock/upload/album",
            data={"album_name": "Night Drive", "play_now": "false"},
            files=[
                ("files", ("01.mp3", b"aaa", "audio/mpeg")),
                ("files", ("02.flac", b"bbb", "audio/flac")),
            ],
        )

    assert res.status_code == 200
    body = res.json()
    assert body["album"] == "Night Drive"
    assert body["count"] == 2
    album_dir = Path(instance.music_dir) / "Night Drive"
    assert (album_dir / "01.mp3").exists()
    assert (album_dir / "02.flac").exists()
