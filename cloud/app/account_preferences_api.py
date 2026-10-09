from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Base, User
from .security import get_current_user, get_session
from .config import get_settings
from .schemas import SUPPORTED_LANGUAGES


class AccountPreferences(Base):
    __tablename__ = "account_preferences"
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    theme: Mapped[str] = mapped_column(String(12), default="light", nullable=False)
    avatar_key: Mapped[str | None] = mapped_column(String(100), nullable=True)


class PreferencesPatch(BaseModel):
    language: str | None = None
    theme: str | None = None


router = APIRouter(prefix="/api/v1/account", tags=["account-preferences"])


async def _get_or_create(session: AsyncSession, user: User) -> AccountPreferences:
    row = await session.get(AccountPreferences, user.id)
    if row is None:
        row = AccountPreferences(user_id=user.id, theme="light")
        session.add(row)
    return row


def _payload(user: User, row: AccountPreferences) -> dict:
    return {
        "language": user.preferred_language,
        "theme": row.theme,
        "avatar_url": f"/api/v1/account/avatar" if row.avatar_key else None,
        "supported_languages": list(SUPPORTED_LANGUAGES),
    }


@router.get("/preferences")
async def get_preferences(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    row = await _get_or_create(session, user)
    return _payload(user, row)


@router.patch("/preferences")
async def update_preferences(
    payload: PreferencesPatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    row = await _get_or_create(session, user)
    if payload.language is not None:
        if payload.language not in SUPPORTED_LANGUAGES:
            raise HTTPException(422, "Unsupported language")
        user.preferred_language = payload.language
    if payload.theme is not None:
        if payload.theme not in ("light", "dark"):
            raise HTTPException(422, "Unsupported theme")
        row.theme = payload.theme
    await session.commit()
    return _payload(user, row)


@router.post("/avatar")
async def upload_avatar(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if request.headers.get("content-type", "").split(";")[0] not in (
        "image/jpeg", "image/png", "image/webp",
    ):
        raise HTTPException(415, "JPEG, PNG or WebP required")
    data = await request.body()
    if len(data) > 2_097_152 or len(data) < 32:
        raise HTTPException(413, "Avatar must be 2 MB or less")
    if data.startswith(bytes.fromhex("ffd8ff")):
        ext = ".jpg"
    elif data.startswith(bytes.fromhex("89504e470d0a1a0a")):
        ext = ".png"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        ext = ".webp"
    else:
        raise HTTPException(415, "Invalid image format")
    row = await _get_or_create(session, user)
    directory = Path(get_settings().photo_dir) / "avatars"
    directory.mkdir(parents=True, exist_ok=True)
    name = uuid4().hex + ext
    destination = directory / name
    destination.write_bytes(data)
    previous = row.avatar_key
    row.avatar_key = name
    try:
        await session.commit()
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    if previous:
        (directory / previous).unlink(missing_ok=True)
    return _payload(user, row)


@router.get("/avatar", response_class=FileResponse)
async def read_avatar(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(AccountPreferences, user.id)
    if row is None or not row.avatar_key:
        raise HTTPException(404, "Avatar not found")
    path = Path(get_settings().photo_dir) / "avatars" / row.avatar_key
    if not path.is_file():
        raise HTTPException(404, "Avatar not found")
    content_type = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[path.suffix]
    return FileResponse(path, media_type=content_type, headers={"Cache-Control": "private, no-store"})
