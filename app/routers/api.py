"""REST API for MPD control and uploads."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app import mpd_client
from app.config import get_instance, get_settings
from app.uploads import UploadError, save_album, save_track

router = APIRouter(prefix="/api")


class VolumeBody(BaseModel):
    level: int = Field(ge=0, le=100)


class SeekBody(BaseModel):
    seconds: float = Field(ge=0)


class OptionBody(BaseModel):
    enabled: bool


class PlayBody(BaseModel):
    pos: int | None = None


class AddBody(BaseModel):
    uri: str
    play_now: bool = False


def _instance_or_404(instance_id: str):
    try:
        return get_instance(instance_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown instance: {instance_id}") from exc


def _mpd_http_error(exc: mpd_client.MpdError) -> HTTPException:
    return HTTPException(status_code=503 if exc.offline else 400, detail=str(exc))


@router.get("/health")
async def health() -> dict:
    return {"ok": True, "version": "1.0.0"}


@router.get("/instances")
async def list_instances() -> dict:
    settings = get_settings()
    statuses = []
    for instance in settings.instances:
        statuses.append(await mpd_client.get_status(instance))
    return {"instances": statuses}


@router.get("/instances/{instance_id}")
async def instance_status(instance_id: str) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await mpd_client.get_status(instance)
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.post("/instances/{instance_id}/play")
async def play(instance_id: str, body: PlayBody | None = None) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await mpd_client.play(instance, None if body is None else body.pos)
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.post("/instances/{instance_id}/pause")
async def pause(instance_id: str) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await mpd_client.pause(instance, True)
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.post("/instances/{instance_id}/toggle")
async def toggle(instance_id: str) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await mpd_client.toggle(instance)
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.post("/instances/{instance_id}/stop")
async def stop(instance_id: str) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await mpd_client.stop(instance)
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.post("/instances/{instance_id}/next")
async def next_track(instance_id: str) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await mpd_client.next_track(instance)
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.post("/instances/{instance_id}/previous")
async def previous_track(instance_id: str) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await mpd_client.previous_track(instance)
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.post("/instances/{instance_id}/volume")
async def volume(instance_id: str, body: VolumeBody) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await mpd_client.set_volume(instance, body.level)
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.post("/instances/{instance_id}/seek")
async def seek(instance_id: str, body: SeekBody) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await mpd_client.seek(instance, body.seconds)
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.post("/instances/{instance_id}/options/{option}")
async def set_option(instance_id: str, option: str, body: OptionBody) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await mpd_client.set_option(instance, option, body.enabled)
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.post("/instances/{instance_id}/update")
async def update_db(instance_id: str) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        result = await mpd_client.update_db(instance)
        status = await mpd_client.get_status(instance)
        return {**result, "status": status}
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.post("/instances/{instance_id}/playlist/clear")
async def clear_playlist(instance_id: str) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await mpd_client.clear_playlist(instance)
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.post("/instances/{instance_id}/playlist/add")
async def add_uri(instance_id: str, body: AddBody) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await mpd_client.add_to_playlist(instance, body.uri, play_now=body.play_now)
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.get("/instances/{instance_id}/playlist")
async def playlist(instance_id: str) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        songs = await mpd_client.get_playlist(instance)
        return {"playlist": songs}
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.get("/instances/{instance_id}/library")
async def library(
    instance_id: str, path: Annotated[str, Query()] = ""
) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await mpd_client.list_library(instance, path)
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.post("/instances/{instance_id}/upload/track")
async def upload_track(
    instance_id: str,
    file: UploadFile = File(...),
    subdirectory: str | None = Form(default=None),
    play_now: bool = Form(default=False),
) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await save_track(
            instance, file, subdirectory=subdirectory, play_now=play_now
        )
    except UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc


@router.post("/instances/{instance_id}/upload/album")
async def upload_album(
    instance_id: str,
    album_name: str = Form(...),
    files: list[UploadFile] | None = File(default=None),
    archive: UploadFile | None = File(default=None),
    play_now: bool = Form(default=False),
) -> dict:
    instance = _instance_or_404(instance_id)
    try:
        return await save_album(
            instance,
            files or [],
            album_name=album_name,
            archive=archive,
            play_now=play_now,
        )
    except UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except mpd_client.MpdError as exc:
        raise _mpd_http_error(exc) from exc
