from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import User, UserSession
from .schemas import LanguageIn, LoginIn, RegisterIn, UserOut
from .security import (
    SESSION_COOKIE,
    get_current_user,
    get_session,
    hash_password,
    hash_session_token,
    verify_password,
)


router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        preferred_language=user.preferred_language,
        role=user.role,
        email_verified=user.email_verified,
    )


async def create_user_session(session: AsyncSession, user: User, response: Response) -> None:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    raw_token = secrets.token_urlsafe(48)
    session.add(
        UserSession(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=hash_session_token(raw_token),
            expires_at=now + timedelta(days=settings.session_days),
            created_at=now,
        )
    )
    await session.commit()
    response.set_cookie(
        SESSION_COOKIE,
        raw_token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    payload: RegisterIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    existing = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email is already registered")
    now = datetime.now(timezone.utc)
    user = User(
        id=str(uuid4()),
        email=payload.email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        preferred_language=payload.language,
        created_at=now,
    )
    session.add(user)
    await session.flush()
    await create_user_session(session, user, response)
    return user_out(user)


@router.post("/login", response_model=UserOut)
async def login(
    payload: LoginIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    email = payload.email.strip().lower()
    user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    await create_user_session(session, user, response)
    return user_out(user)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    session: AsyncSession = Depends(get_session),
):
    if session_token:
        user_session = (
            await session.execute(
                select(UserSession).where(
                    UserSession.token_hash == hash_session_token(session_token)
                )
            )
        ).scalar_one_or_none()
        if user_session:
            await session.delete(user_session)
            await session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.patch("/me/language", response_model=UserOut)
async def update_language(
    payload: LanguageIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user.preferred_language = payload.language
    await session.commit()
    return user_out(user)
