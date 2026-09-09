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


def _ensure_columns(connection, table_name: str, columns: dict[str, str]) -> None:
    inspector = inspect(connection)
    if table_name not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    for name, definition in columns.items():
        if name not in existing:
            connection.exec_driver_sql(
                f'ALTER TABLE "{table_name}" ADD COLUMN "{name}" {definition}'
            )


def _ensure_plant_image_columns(connection) -> None:
    _ensure_columns(connection, "plants", _PLANT_IMAGE_COLUMNS)


def _ensure_telegram_columns(connection) -> None:
    # The Telegram bot existed before marketplace integration. create_all() does
    # not add columns to existing tables, so keep this small compatibility
    # migration here to preserve current users, balances and social activity.
    is_postgres = connection.dialect.name == "postgresql"
    bool_default = "TRUE" if is_postgres else "1"
    timestamp_type = "TIMESTAMP WITH TIME ZONE" if is_postgres else "DATETIME"

    _ensure_columns(
        connection,
        "telegram_users",
        {
            "marketplace_user_id": "VARCHAR(36) NULL",
        },
    )
    _ensure_columns(
        connection,
        "wallet_transactions",
        {
            "balance_after": "BIGINT NULL",
        },
    )
    _ensure_columns(
        connection,
        "social_follows",
        {
            "notifications_enabled": f"BOOLEAN NOT NULL DEFAULT {bool_default}",
            "last_notified_at": f"{timestamp_type} NULL",
        },
    )

    tables = inspect(connection).get_table_names()
    if "social_follows" in tables:
        # Existing follows predate last_notified_at. Starting from created_at
        # prevents an old subscription from being permanently excluded from
        # the new-photo notification query.
        connection.exec_driver_sql(
            "UPDATE social_follows SET last_notified_at = created_at "
            "WHERE last_notified_at IS NULL"
        )

    # Keep linking optional for now. The partial integration must not fail when
    # older Telegram rows have no marketplace account.
    if "telegram_users" in tables:
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_telegram_users_marketplace_user_id "
            "ON telegram_users (marketplace_user_id)"
        )


async def create_tables() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_ensure_plant_image_columns)
        await connection.run_sync(_ensure_telegram_columns)
