from __future__ import annotations

import hashlib
import secrets

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .db import SessionLocal
from .models import Device


bearer_scheme = HTTPBearer(auto_error=False)


def hash_device_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def get_session():
    async with SessionLocal() as session:
        yield session


async def authenticate_device(
    x_device_id: str = Header(alias="X-Device-ID"),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> Device:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Device authentication required")

    device = await session.get(Device, x_device_id)
    supplied_hash = hash_device_token(credentials.credentials)
    if (
        device is None
        or not device.is_active
        or not secrets.compare_digest(device.token_hash, supplied_hash)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device credentials")

    return device
