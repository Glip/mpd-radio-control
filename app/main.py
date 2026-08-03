"""MPD Radio Control Panel entrypoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import __version__
from app.config import get_settings
from app.routers.api import router as api_router

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Radio Desk",
    description="Control panel for multiple MPD internet-radio instances",
    version=__version__,
)
app.include_router(api_router)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    settings = get_settings()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "instances": [
                {"id": i.id, "label": i.label, "host": i.host, "port": i.port}
                for i in settings.instances
            ],
            "version": __version__,
        },
    )


def create_app() -> FastAPI:
    return app
