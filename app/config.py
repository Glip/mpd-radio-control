"""Application configuration loaded from environment variables."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class MpdInstance:
    """One MPD endpoint the panel can control."""

    id: str
    host: str
    port: int
    music_dir: str
    label: str
    password: str | None = None


_INSTANCE_RE = re.compile(
    r"^(?P<id>[^:]+):(?P<host>[^:]+):(?P<port>\d+)(?::(?P<music_dir>[^:]*))?(?::(?P<label>.*))?$"
)


def _parse_csv_instances(raw: str) -> list[MpdInstance]:
    """
    Parse MPD_INSTANCES CSV format:
      id:host:port[:music_dir[:label]]
    Multiple instances separated by commas.
    Example: rock:mpd-rock:6600:/music/rock:Rock Radio,jazz:mpd-jazz:6600:/music/jazz
    """
    instances: list[MpdInstance] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        match = _INSTANCE_RE.match(chunk)
        if not match:
            raise ValueError(
                f"Invalid MPD_INSTANCES entry: {chunk!r}. "
                "Expected id:host:port[:music_dir[:label]]"
            )
        instance_id = match.group("id").strip()
        host = match.group("host").strip()
        port = int(match.group("port"))
        music_dir = (match.group("music_dir") or "").strip() or f"/music/{instance_id}"
        label = (match.group("label") or "").strip() or instance_id
        password = os.getenv(f"MPD_PASSWORD_{instance_id.upper().replace('-', '_')}")
        instances.append(
            MpdInstance(
                id=instance_id,
                host=host,
                port=port,
                music_dir=music_dir,
                label=label,
                password=password or None,
            )
        )
    return instances


def _parse_json_instances(raw: str) -> list[MpdInstance]:
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("MPD_INSTANCES_JSON must be a JSON array")
    instances: list[MpdInstance] = []
    for item in data:
        instance_id = str(item["id"]).strip()
        password = item.get("password") or os.getenv(
            f"MPD_PASSWORD_{instance_id.upper().replace('-', '_')}"
        )
        instances.append(
            MpdInstance(
                id=instance_id,
                host=str(item["host"]).strip(),
                port=int(item["port"]),
                music_dir=str(item.get("music_dir") or f"/music/{instance_id}"),
                label=str(item.get("label") or instance_id),
                password=password or None,
            )
        )
    return instances


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the control panel."""

    instances: tuple[MpdInstance, ...]
    host: str = "0.0.0.0"
    port: int = 8080
    mpd_timeout: float = 5.0
    max_upload_mb: int = 500
    allowed_audio_ext: tuple[str, ...] = (
        ".mp3",
        ".flac",
        ".ogg",
        ".oga",
        ".opus",
        ".m4a",
        ".aac",
        ".wav",
        ".wma",
        ".aiff",
        ".aif",
    )


@lru_cache
def get_settings() -> Settings:
    json_raw = os.getenv("MPD_INSTANCES_JSON", "").strip()
    csv_raw = os.getenv("MPD_INSTANCES", "").strip()

    if json_raw:
        instances = _parse_json_instances(json_raw)
    elif csv_raw:
        instances = _parse_csv_instances(csv_raw)
    else:
        # Sensible local/dev default matching docker-compose.yml
        instances = [
            MpdInstance(
                id="rock",
                host=os.getenv("MPD_HOST_ROCK", "mpd-rock"),
                port=int(os.getenv("MPD_PORT_ROCK", "6600")),
                music_dir="/music/rock",
                label="Rock Radio",
            ),
            MpdInstance(
                id="jazz",
                host=os.getenv("MPD_HOST_JAZZ", "mpd-jazz"),
                port=int(os.getenv("MPD_PORT_JAZZ", "6600")),
                music_dir="/music/jazz",
                label="Jazz Radio",
            ),
        ]

    if not instances:
        raise ValueError("At least one MPD instance must be configured")

    ids = [i.id for i in instances]
    if len(ids) != len(set(ids)):
        raise ValueError("MPD instance ids must be unique")

    return Settings(
        instances=tuple(instances),
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8080")),
        mpd_timeout=float(os.getenv("MPD_TIMEOUT", "5")),
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "500")),
    )


def get_instance(instance_id: str) -> MpdInstance:
    settings = get_settings()
    for instance in settings.instances:
        if instance.id == instance_id:
            return instance
    raise KeyError(instance_id)
