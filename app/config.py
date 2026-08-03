"""Application configuration loaded from a mounted YAML file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DEFAULT_AUDIO_EXT = (
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

# Search order for the config file. Override with RADIO_DESK_CONFIG=/path/to.yaml
CONFIG_CANDIDATES = (
    Path("/config/config.yaml"),
    Path("/config/radio-desk.yaml"),
    Path("config/config.yaml"),
)


@dataclass(frozen=True)
class MpdInstance:
    """One MPD endpoint the panel can control."""

    id: str
    host: str
    port: int
    music_dir: str
    label: str
    password: str | None = None


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the control panel."""

    instances: tuple[MpdInstance, ...]
    host: str = "0.0.0.0"
    port: int = 8080
    mpd_timeout: float = 5.0
    max_upload_mb: int = 500
    config_path: str | None = None
    allowed_audio_ext: tuple[str, ...] = DEFAULT_AUDIO_EXT


def resolve_config_path(explicit: str | None = None) -> Path:
    """Return the first existing config path."""
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Config file not found: {path}")
        return path.resolve()

    env_path = os.getenv("RADIO_DESK_CONFIG", "").strip()
    if env_path:
        path = Path(env_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(
                f"RADIO_DESK_CONFIG points to missing file: {path}"
            )
        return path.resolve()

    for candidate in CONFIG_CANDIDATES:
        if candidate.is_file():
            return candidate.resolve()

    searched = ", ".join(str(p) for p in CONFIG_CANDIDATES)
    raise FileNotFoundError(
        "No config file found. Mount a YAML config to /config/config.yaml "
        f"or set RADIO_DESK_CONFIG. Searched: {searched}"
    )


def _parse_instances(raw: Any) -> list[MpdInstance]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("Config key 'instances' must be a non-empty list")

    instances: list[MpdInstance] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"instances[{index}] must be a mapping")
        try:
            instance_id = str(item["id"]).strip()
            host = str(item["host"]).strip()
            port = int(item["port"])
        except KeyError as exc:
            raise ValueError(
                f"instances[{index}] is missing required field: {exc.args[0]}"
            ) from exc
        except (TypeError, ValueError) as exc:
            raise ValueError(f"instances[{index}].port must be an integer") from exc

        if not instance_id:
            raise ValueError(f"instances[{index}].id must not be empty")
        if not host:
            raise ValueError(f"instances[{index}].host must not be empty")

        music_dir = str(item.get("music_dir") or f"/music/{instance_id}").strip()
        label = str(item.get("label") or instance_id).strip()
        password = item.get("password")
        if password is not None:
            password = str(password) or None

        instances.append(
            MpdInstance(
                id=instance_id,
                host=host,
                port=port,
                music_dir=music_dir,
                label=label,
                password=password,
            )
        )
    return instances


def load_settings_from_file(path: Path) -> Settings:
    """Parse Settings from a YAML config file."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config root in {path} must be a mapping")

    server = raw.get("server") or {}
    if not isinstance(server, dict):
        raise ValueError("Config key 'server' must be a mapping")

    instances = _parse_instances(raw.get("instances"))
    ids = [i.id for i in instances]
    if len(ids) != len(set(ids)):
        raise ValueError("MPD instance ids must be unique")

    exts = server.get("allowed_audio_ext")
    if exts is None:
        allowed = DEFAULT_AUDIO_EXT
    else:
        if not isinstance(exts, list) or not exts:
            raise ValueError("server.allowed_audio_ext must be a non-empty list")
        allowed = tuple(
            e if str(e).startswith(".") else f".{e}" for e in (str(x).lower() for x in exts)
        )

    return Settings(
        instances=tuple(instances),
        host=str(server.get("host") or "0.0.0.0"),
        port=int(server.get("port") or 8080),
        mpd_timeout=float(server.get("mpd_timeout") or 5),
        max_upload_mb=int(server.get("max_upload_mb") or 500),
        config_path=str(path),
        allowed_audio_ext=allowed,
    )


@lru_cache
def get_settings() -> Settings:
    path = resolve_config_path()
    return load_settings_from_file(path)


def get_instance(instance_id: str) -> MpdInstance:
    settings = get_settings()
    for instance in settings.instances:
        if instance.id == instance_id:
            return instance
    raise KeyError(instance_id)
