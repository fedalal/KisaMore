from __future__ import annotations

import asyncio
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import PasswordResetToken, User, UserSession
from .schemas import (
    LanguageIn,
    LoginIn,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    RegisterIn,
    UserOut,
)
from .security import (
    SESSION_COOKIE,
    get_current_user,
    get_session,
    hash_password,
    hash_session_token,
    verify_password,
)


router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def _password_reset_email(user: User, reset_url: str) -> tuple[str, str]:
    if user.preferred_language == "ru":
        subject = "KisaMore — восстановление пароля"
        body = (
            f"Здравствуйте, {user.display_name}!\n\n"
            "Для установки нового пароля откройте ссылку:\n"
            f"{reset_url}\n\n"
            "Ссылка действует 30 минут и может быть использована только один раз.\n"
            "Если вы не запрашивали восстановление пароля, просто проигнорируйте это письмо.\n\n"
            "KisaMore"
        )
    else:
        subject = "KisaMore — reset your password"
        body = (
            f"Hello, {user.display_name}!\n\n"
            "Open this link to set a new password:\n"
            f"{reset_url}\n\n"
            "The link is valid for 30 minutes and can be used only once.\n"
            "If you did not request a password reset, you can ignore this email.\n\n"
            "KisaMore"
        )
    return subject, body


def _send_password_reset_email(user: User, reset_url: str) -> None:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from_email:
        raise RuntimeError("Password reset email is not configured")

    subject, body = _password_reset_email(user, reset_url)
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = user.email
    message.set_content(body)

    smtp_factory = (
        smtplib.SMTP_SSL
        if settings.smtp_port == 465 and not settings.smtp_starttls
        else smtplib.SMTP
    )
    with smtp_factory(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


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


@router.post("/password-reset/request", status_code=202)
async def request_password_reset(
    payload: PasswordResetRequestIn,
    session: AsyncSession = Depends(get_session),
):
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from_email:
        raise HTTPException(
            status_code=503,
            detail="Password recovery email is not configured",
        )

    user = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()

    # Always return the same response for unknown addresses.
    if user is None or not user.is_active:
        return {"ok": True}

    now = datetime.now(timezone.utc)
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_session_token(raw_token)

    await session.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    )
    session.add(
        PasswordResetToken(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(minutes=30),
            used_at=None,
            created_at=now,
        )
    )
    await session.commit()

    reset_url = f"{settings.public_base_url}/?reset_token={raw_token}"
    try:
        await asyncio.to_thread(_send_password_reset_email, user, reset_url)
    except Exception:
        await session.execute(
            delete(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
        )
        await session.commit()
        raise HTTPException(
            status_code=503,
            detail="Could not send password recovery email",
        )

    return {"ok": True}


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    payload: PasswordResetConfirmIn,
    session: AsyncSession = Depends(get_session),
):
    now = datetime.now(timezone.utc)
    token_hash = hash_session_token(payload.token)
    reset_token = (
        await session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if reset_token is None:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")

    expires_at = reset_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")

    user = await session.get(User, reset_token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")

    user.password_hash = hash_password(payload.password)
    reset_token.used_at = now

    # Sign out all existing sessions after a password reset.
    await session.execute(delete(UserSession).where(UserSession.user_id == user.id))
    await session.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != reset_token.id,
        )
    )
    await session.commit()
    return {"ok": True}


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
