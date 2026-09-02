from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings
from .models import Base


settings = get_settings()

if settings.database_url.startswith("sqlite"):
    db_path = settings.database_url.rsplit("///", 1)[-1]
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

_PLANT_IMAGE_COLUMNS = {
    "seed_image_name": "VARCHAR(255) NOT NULL DEFAULT ''",
    "microgreen_image_name": "VARCHAR(255) NOT NULL DEFAULT ''",
}


def _ensure_plant_image_columns(connection) -> None:
    inspector = inspect(connection)
    if "plants" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("plants")}
    for name, definition in _PLANT_IMAGE_COLUMNS.items():
        if name not in existing:
            connection.exec_driver_sql(f"ALTER TABLE plants ADD COLUMN {name} {definition}")


async def create_tables() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_ensure_plant_image_columns)
