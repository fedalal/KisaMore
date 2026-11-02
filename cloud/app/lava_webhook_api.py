"""Lava.top authenticated webhook: records delivery, never credits wallets."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from .lava_webhook_models import LavaWebhookEvent
from .security import get_session

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

def _authenticated(header: str | None) -> bool:
    username = os.getenv("KISAMORE_LAVA_WEBHOOK_USER", "")
    password = os.getenv("KISAMORE_LAVA_WEBHOOK_PASSWORD", "")
    if not username or len(password) < 24 or not header:
        return False
    scheme, separator, credential = header.partition(" ")
    if not separator or scheme.lower() != "basic":
        return False
    try:
        decoded = base64.b64decode(credential, validate=True).decode("utf-8")
        supplied_user, colon, supplied_password = decoded.partition(":")
        if not colon:
            return False
    except (ValueError, UnicodeError):
        return False
    return hmac.compare_digest(username, supplied_user) and hmac.compare_digest(password, supplied_password)

@router.get("/catalog")
async def payment_catalog():
    return {"enabled": False, "topup_enabled": False, "subscription_enabled": False}

@router.post("/lava/webhook")
async def lava_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    if not os.getenv("KISAMORE_LAVA_WEBHOOK_USER") or len(os.getenv("KISAMORE_LAVA_WEBHOOK_PASSWORD", "")) < 24:
        raise HTTPException(status_code=503, detail="Webhook receiver is not configured")
    if not _authenticated(request.headers.get("authorization")):
        raise HTTPException(status_code=401, detail="Webhook authentication required",
                            headers={"WWW-Authenticate": 'Basic realm="KisaMore Lava Webhook"'})
    if request.headers.get("content-length"):
        try:
            if int(request.headers["content-length"]) > 65536:
                raise HTTPException(status_code=413, detail="Webhook too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid content-length")
    body = await request.body()
    if len(body) > 65536:
        raise HTTPException(status_code=413, detail="Webhook too large")
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object")
    event_type = payload.get("event_type") or payload.get("eventType") or "unknown"
    event_type = event_type[:100] if isinstance(event_type, str) else "unknown"
    inner = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    invoice = inner.get("invoiceId") or inner.get("invoice_id") or inner.get("contractId") or inner.get("contract_id")
    invoice_id = str(invoice)[:128] if invoice is not None else None
    event_id = payload.get("event_id") or payload.get("eventId")
    digest = hashlib.sha256(body).hexdigest()
    # Flat events may lack event ID; never deduplicate on contractId alone.
    event_key = ("id:" + str(event_id)[:120]) if event_id else "sha256:" + digest
    session.add(LavaWebhookEvent(event_key=event_key, event_type=event_type,
                                 invoice_id=invoice_id, payload=payload,
                                 status="received_unprocessed"))
    try:
        await session.commit()
        duplicate = False
    except IntegrityError:
        await session.rollback()
        duplicate = True
    # No entitlements until invoice->user mapping and provider verification.
    # Return 2xx on unknown event types per Lava.top documentation.
    return {"received": True, "duplicate": duplicate, "processed": False}
