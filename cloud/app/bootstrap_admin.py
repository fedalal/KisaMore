from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal
from .models import User
from .security import hash_password


async def bootstrap_admin() -> None:
    settings = get_settings()
    email = settings.admin_email.strip().lower()
    if not email:
        print("[admin] bootstrap disabled: KISAMORE_ADMIN_EMAIL is empty")
        return

    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

        if user is None:
            if len(settings.admin_password) < 12:
                print("[admin] bootstrap skipped: KISAMORE_ADMIN_PASSWORD must be at least 12 characters")
                return
            user = User(
                id=str(uuid4()),
                email=email,
                display_name=settings.admin_name or "KisaMore Admin",
                password_hash=hash_password(settings.admin_password),
                preferred_language="ru",
                role="admin",
                email_verified=True,
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            session.add(user)
            await session.commit()
            print(f"[admin] administrator created: {email}")
            return

        changed = False
        if user.role != "admin":
            user.role = "admin"
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if settings.admin_name and user.display_name != settings.admin_name:
            user.display_name = settings.admin_name
            changed = True
        if changed:
            await session.commit()
            print(f"[admin] administrator role ensured: {email}")
