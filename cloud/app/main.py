from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .bootstrap import bootstrap_first_device
from .config import get_settings
from .db import create_tables, engine


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
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Device-ID"],
    )

app.include_router(router)
