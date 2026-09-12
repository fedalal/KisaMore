from __future__ import annotations

from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .admin_api import router as admin_router
from .admin_camera_api import router as admin_camera_router
from .api import router
from .auth_api import router as auth_router
from .bootstrap import bootstrap_first_device
from .bootstrap_admin import bootstrap_admin
from .config import get_settings
from .db import create_tables, engine
from .marketplace_api import router as marketplace_router
from .mqtt_sync import mqtt_snapshot_consumer
from .mqtt_photo_sync import mqtt_photo_consumer
from .rack_photo_api import router as rack_photo_router
from .rack_photo_bootstrap import backfill_rack_photo_derivatives
from .rental_admin_api import router as rental_admin_router
from .rental_progress_admin_api import router as rental_progress_admin_router
from .seed_inventory_admin_api import router as seed_inventory_admin_router
from .telegram_admin_api import router as telegram_admin_router
from .telegram_message_admin_api import router as telegram_message_admin_router
from .timelapse_api import router as timelapse_router
from .watering_admin_api import router as watering_admin_router


STATIC_DIR = Path(__file__).resolve().parent / "static"
DASHBOARD_TEMPLATE = STATIC_DIR / "index.html"
ADMIN_TEMPLATE = STATIC_DIR / "admin.html"


@asynccontextmanager
async def lifespan(_: FastAPI):
    await create_tables()
    await bootstrap_first_device()
    await bootstrap_admin()
    await backfill_rack_photo_derivatives()
    await mqtt_snapshot_consumer.start()
    await mqtt_photo_consumer.start()
    yield
    await mqtt_photo_consumer.stop()
    await mqtt_snapshot_consumer.stop()
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
    return HTMLResponse(content, headers={"Cache-Control": "no-cache"})


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_dashboard() -> HTMLResponse:
    content = ADMIN_TEMPLATE.read_text(encoding="utf-8").replace(
        "/static/admin_telegram.js?v=20260910-1",
        "/static/admin_telegram.js?v=20260912-3",
    )
    return HTMLResponse(
        content,
        headers={"Cache-Control": "no-cache"},
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(router)
app.include_router(auth_router)
app.include_router(marketplace_router)
app.include_router(rack_photo_router)
app.include_router(timelapse_router)
app.include_router(admin_router)
app.include_router(admin_camera_router)
app.include_router(rental_admin_router)
app.include_router(rental_progress_admin_router)
app.include_router(watering_admin_router)
app.include_router(seed_inventory_admin_router)
app.include_router(telegram_admin_router)
app.include_router(telegram_message_admin_router)
