"""Helpers for uploading tracks and albums into MPD music directories."""

from __future__ import annotations

import asyncio
import re
import shutil
import zipfile
from pathlib import Path

import aiofiles
from fastapi import UploadFile

from app.config import MpdInstance, get_settings
from app import mpd_client

_SAFE_NAME_RE = re.compile(r"[^\w.\- ()\[\]]+", re.UNICODE)
_UNSAFE_PATH_RE = re.compile(r"[\\/]+")


class UploadError(Exception):
    """Raised when an upload cannot be stored safely."""


def _sanitize_name(name: str) -> str:
    name = name.strip().replace("\x00", "")
    name = _UNSAFE_PATH_RE.sub("-", name)
    name = _SAFE_NAME_RE.sub("_", name)
    name = name.strip(" ._")
    if not name or name in {".", ".."}:
        raise UploadError("Invalid file name")
    return name[:180]


def _is_allowed_audio(filename: str) -> bool:
    settings = get_settings()
    return Path(filename).suffix.lower() in settings.allowed_audio_ext


def music_root(instance: MpdInstance) -> Path:
    root = Path(instance.music_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _ensure_inside(root: Path, target: Path) -> Path:
    resolved = target.resolve()
    if not str(resolved).startswith(str(root.resolve()) + "/") and resolved != root.resolve():
        raise UploadError("Path escapes music directory")
    return resolved


async def _write_upload(dest: Path, upload: UploadFile, max_bytes: int) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    async with aiofiles.open(dest, "wb") as out:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                await out.close()
                dest.unlink(missing_ok=True)
                raise UploadError(
                    f"File exceeds max upload size ({max_bytes // (1024 * 1024)} MB)"
                )
            await out.write(chunk)
    return written


async def save_track(
    instance: MpdInstance,
    upload: UploadFile,
    *,
    subdirectory: str | None = None,
    play_now: bool = False,
) -> dict:
    if not upload.filename:
        raise UploadError("Missing filename")
    if not _is_allowed_audio(upload.filename):
        raise UploadError(
            f"Unsupported audio type: {Path(upload.filename).suffix or '(none)'}"
        )

    root = music_root(instance)
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024

    filename = _sanitize_name(Path(upload.filename).name)
    if subdirectory:
        sub = _sanitize_name(subdirectory)
        dest = _ensure_inside(root, root / sub / filename)
        rel_uri = f"{sub}/{filename}"
    else:
        dest = _ensure_inside(root, root / filename)
        rel_uri = filename

    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        n = 1
        while dest.exists():
            candidate = dest.with_name(f"{stem}_{n}{suffix}")
            dest = _ensure_inside(root, candidate)
            n += 1
        rel_uri = str(dest.relative_to(root)).replace("\\", "/")

    size = await _write_upload(dest, upload, max_bytes)
    await mpd_client.update_db(instance, str(Path(rel_uri).parent).replace("\\", "/") if "/" in rel_uri else "")
    # Give MPD a moment, then add
    await asyncio.sleep(0.3)
    status = await mpd_client.add_to_playlist(instance, rel_uri, play_now=play_now)
    return {
        "file": rel_uri,
        "bytes": size,
        "path": str(dest),
        "status": status,
    }


async def save_album(
    instance: MpdInstance,
    files: list[UploadFile],
    *,
    album_name: str,
    archive: UploadFile | None = None,
    play_now: bool = False,
) -> dict:
    album = _sanitize_name(album_name)
    root = music_root(instance)
    album_dir = _ensure_inside(root, root / album)
    if album_dir.exists() and any(album_dir.iterdir()):
        # keep existing album, nest uniquely
        n = 1
        while True:
            candidate = root / f"{album}_{n}"
            if not candidate.exists():
                album_dir = _ensure_inside(root, candidate)
                album = album_dir.name
                break
            n += 1

    album_dir.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    saved: list[str] = []

    if archive is not None:
        if not archive.filename or not archive.filename.lower().endswith(".zip"):
            raise UploadError("Album archive must be a .zip file")
        tmp_zip = album_dir / "_upload.zip"
        await _write_upload(tmp_zip, archive, max_bytes)
        try:
            saved = await asyncio.to_thread(_extract_zip_audio, tmp_zip, album_dir)
        finally:
            tmp_zip.unlink(missing_ok=True)
    else:
        if not files:
            raise UploadError("No album files provided")
        for upload in files:
            if not upload.filename or not _is_allowed_audio(upload.filename):
                continue
            filename = _sanitize_name(Path(upload.filename).name)
            dest = _ensure_inside(album_dir, album_dir / filename)
            await _write_upload(dest, upload, max_bytes)
            saved.append(filename)

    if not saved:
        shutil.rmtree(album_dir, ignore_errors=True)
        raise UploadError("No supported audio files found in upload")

    await mpd_client.update_db(instance, album)
    await asyncio.sleep(0.5)

    def _add_album(client) -> None:
        if play_now:
            client.clear()
        client.add(album)
        if play_now:
            client.play()

    await mpd_client.run_mpd(instance, _add_album)
    status = await mpd_client.get_status(instance)
    return {
        "album": album,
        "files": saved,
        "count": len(saved),
        "status": status,
    }


def _extract_zip_audio(zip_path: Path, dest_dir: Path) -> list[str]:
    saved: list[str] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename).name
            if name.startswith(".") or name.startswith("__MACOSX"):
                continue
            if not _is_allowed_audio(name):
                continue
            safe = _sanitize_name(name)
            target = dest_dir / safe
            # avoid overwrite collisions
            if target.exists():
                stem, suffix = target.stem, target.suffix
                n = 1
                while target.exists():
                    target = dest_dir / f"{stem}_{n}{suffix}"
                    n += 1
                    safe = target.name
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            saved.append(safe)
    return saved
