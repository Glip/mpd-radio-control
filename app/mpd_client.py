"""Thin async-friendly wrapper around python-mpd2."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Any, Callable, TypeVar

from mpd import CommandError, ConnectionError as MpdConnectionError, MPDClient

from app.config import MpdInstance, get_settings

T = TypeVar("T")


class MpdError(Exception):
    """Raised when an MPD command fails."""

    def __init__(self, message: str, *, offline: bool = False):
        super().__init__(message)
        self.offline = offline


@contextmanager
def _connected(instance: MpdInstance):
    settings = get_settings()
    client = MPDClient()
    client.timeout = settings.mpd_timeout
    client.idletimeout = None
    try:
        client.connect(instance.host, instance.port)
        if instance.password:
            client.password(instance.password)
        yield client
    except (MpdConnectionError, OSError, TimeoutError) as exc:
        raise MpdError(
            f"Cannot reach MPD '{instance.id}' at {instance.host}:{instance.port}: {exc}",
            offline=True,
        ) from exc
    except CommandError as exc:
        raise MpdError(str(exc)) from exc
    finally:
        try:
            client.close()
        except Exception:
            pass
        try:
            client.disconnect()
        except Exception:
            pass


async def run_mpd(instance: MpdInstance, fn: Callable[[MPDClient], T]) -> T:
    """Run a blocking MPD call in a worker thread."""

    def _call() -> T:
        with _connected(instance) as client:
            return fn(client)

    try:
        return await asyncio.to_thread(_call)
    except MpdError:
        raise
    except CommandError as exc:
        raise MpdError(str(exc)) from exc


def _song_payload(song: dict[str, Any] | None) -> dict[str, Any] | None:
    if not song:
        return None
    return {
        "file": song.get("file"),
        "title": song.get("title") or song.get("file"),
        "artist": song.get("artist") or "",
        "album": song.get("album") or "",
        "time": song.get("time"),
        "duration": song.get("duration") or song.get("time"),
        "pos": song.get("pos"),
        "id": song.get("id"),
    }


async def get_status(instance: MpdInstance) -> dict[str, Any]:
    def _status(client: MPDClient) -> dict[str, Any]:
        status = client.status()
        current = client.currentsong() or {}
        return {
            "id": instance.id,
            "label": instance.label,
            "host": instance.host,
            "port": instance.port,
            "online": True,
            "state": status.get("state", "stop"),
            "volume": int(status.get("volume", -1)),
            "repeat": status.get("repeat") == "1",
            "random": status.get("random") == "1",
            "single": status.get("single") == "1",
            "consume": status.get("consume") == "1",
            "playlist_length": int(status.get("playlistlength", 0)),
            "song_pos": int(status["song"]) if "song" in status else None,
            "elapsed": float(status["elapsed"]) if "elapsed" in status else None,
            "duration": float(status["duration"]) if "duration" in status else None,
            "bitrate": status.get("bitrate"),
            "audio": status.get("audio"),
            "error": status.get("error"),
            "current": _song_payload(current),
        }

    try:
        return await run_mpd(instance, _status)
    except MpdError as exc:
        if exc.offline:
            return {
                "id": instance.id,
                "label": instance.label,
                "host": instance.host,
                "port": instance.port,
                "online": False,
                "state": "offline",
                "volume": None,
                "repeat": False,
                "random": False,
                "single": False,
                "consume": False,
                "playlist_length": 0,
                "song_pos": None,
                "elapsed": None,
                "duration": None,
                "bitrate": None,
                "audio": None,
                "error": str(exc),
                "current": None,
            }
        raise


async def play(instance: MpdInstance, pos: int | None = None) -> dict[str, Any]:
    def _play(client: MPDClient) -> None:
        if pos is None:
            client.play()
        else:
            client.play(pos)

    await run_mpd(instance, _play)
    return await get_status(instance)


async def pause(instance: MpdInstance, paused: bool = True) -> dict[str, Any]:
    await run_mpd(instance, lambda c: c.pause(1 if paused else 0))
    return await get_status(instance)


async def toggle(instance: MpdInstance) -> dict[str, Any]:
    def _toggle(client: MPDClient) -> None:
        status = client.status()
        state = status.get("state")
        if state == "play":
            client.pause(1)
        else:
            client.play()

    await run_mpd(instance, _toggle)
    return await get_status(instance)


async def stop(instance: MpdInstance) -> dict[str, Any]:
    await run_mpd(instance, lambda c: c.stop())
    return await get_status(instance)


async def next_track(instance: MpdInstance) -> dict[str, Any]:
    await run_mpd(instance, lambda c: c.next())
    return await get_status(instance)


async def previous_track(instance: MpdInstance) -> dict[str, Any]:
    await run_mpd(instance, lambda c: c.previous())
    return await get_status(instance)


async def set_volume(instance: MpdInstance, level: int) -> dict[str, Any]:
    level = max(0, min(100, int(level)))
    await run_mpd(instance, lambda c: c.setvol(level))
    return await get_status(instance)


async def seek(instance: MpdInstance, seconds: float) -> dict[str, Any]:
    await run_mpd(instance, lambda c: c.seekcur(seconds))
    return await get_status(instance)


async def set_option(instance: MpdInstance, name: str, enabled: bool) -> dict[str, Any]:
    allowed = {"repeat", "random", "single", "consume"}
    if name not in allowed:
        raise MpdError(f"Unknown option: {name}")
    await run_mpd(instance, lambda c: getattr(c, name)(1 if enabled else 0))
    return await get_status(instance)


async def update_db(instance: MpdInstance, uri: str = "") -> dict[str, Any]:
    job = await run_mpd(instance, lambda c: c.update(uri) if uri else c.update())
    return {"updating_db": job}


async def clear_playlist(instance: MpdInstance) -> dict[str, Any]:
    await run_mpd(instance, lambda c: c.clear())
    return await get_status(instance)


async def add_to_playlist(
    instance: MpdInstance, uri: str, *, play_now: bool = False
) -> dict[str, Any]:
    def _add(client: MPDClient) -> None:
        if play_now:
            client.clear()
            client.add(uri)
            client.play()
        else:
            client.add(uri)

    await run_mpd(instance, _add)
    return await get_status(instance)


async def get_playlist(instance: MpdInstance) -> list[dict[str, Any]]:
    songs = await run_mpd(instance, lambda c: c.playlistinfo())
    return [_song_payload(s) for s in songs if s]


async def list_library(instance: MpdInstance, path: str = "") -> dict[str, Any]:
    def _ls(client: MPDClient) -> dict[str, Any]:
        entries = client.lsinfo(path)
        directories: list[str] = []
        files: list[dict[str, Any]] = []
        for entry in entries:
            if "directory" in entry:
                directories.append(entry["directory"])
            elif "file" in entry:
                files.append(_song_payload(entry))  # type: ignore[arg-type]
        return {"path": path, "directories": directories, "files": files}

    return await run_mpd(instance, _ls)
