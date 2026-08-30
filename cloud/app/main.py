from __future__ import annotations

from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .auth_api import router as auth_router
from .marketplace_api import router as marketplace_router
from .bootstrap import bootstrap_first_device
from .config import get_settings
from .db import create_tables, engine


STATIC_DIR = Path(__file__).resolve().parent / "static"
DASHBOARD_TEMPLATE = STATIC_DIR / "index.html"


@asynccontextmanager
async def lifespan(_: FastAPI):
    await create_tables()
    await bootstrap_first_device()
    yield
    await engine.dispose()


app = FastAPI(
    title="KisaMore Cloud API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)

settings = get_settings()
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Device-ID"],
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> HTMLResponse:
    content = DASHBOARD_TEMPLATE.read_text(encoding="utf-8").replace(
        "__KISAMORE_FARM_SLUG__",
        escape(settings.bootstrap_farm_slug, quote=True),
    )
    return HTMLResponse(
        content,
        headers={"Cache-Control": "no-cache"},
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(router)
app.include_router(auth_router)
app.include_router(marketplace_router)
