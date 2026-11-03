"""Lava.top authenticated webhook: records delivery, never credits wallets."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from .lava_webhook_models import LavaWebhookEvent
from .security import get_session

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, Field
from sqlalchemy import select
from .models import User
from .lava_payments_models import LavaOrder, LavaMembership
from .lava_payments_service import (
    enabled, TOPUP_PACKAGES, TOPUP_OFFER, SUBSCRIPTION_OFFER, MONTHLY_PRICE_USD,
    create_lava_invoice, apply_verified_invoice, reconcile_invoice_status, LavaBuyerEmailRejected,
)
from .security import get_current_user, SESSION_COOKIE

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

def test_admin_enabled(user: User | None) -> bool:
    """Only the site admin or one explicitly approved test buyer can test checkout.

    Test buyer is keyed by the immutable website user UUID, never by an
    unverified email address. Public payments remain disabled.
    """
    if not user or not user.is_active or not os.getenv("KISAMORE_LAVA_API_KEY", ""):
        return False
    if os.getenv("KISAMORE_LAVA_TEST_ADMIN_ENABLED", "").strip().lower() != "true":
        return False
    test_buyer_id = os.getenv("KISAMORE_LAVA_TEST_BUYER_ID", "").strip().lower()
    return user.role == "admin" or (
        user.role == "customer" and bool(test_buyer_id)
        and user.id.strip().lower() == test_buyer_id
    )


@router.get("/catalog")
async def payment_catalog(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    session: AsyncSession = Depends(get_session),
):
    admin_user = None
    if session_token:
        try:
            admin_user = await get_current_user(session_token, session)
        except HTTPException:
            pass
    public = enabled()
    tester = test_admin_enabled(admin_user)
    return {
        "enabled": public or tester,
        "topup_enabled": public or tester,
        "subscription_enabled": public,
        "test_mode": tester and not public,
        "packages": list(TOPUP_PACKAGES), "subscription_entries": 3,
        "subscription_price_usd": MONTHLY_PRICE_USD,
    }


class CheckoutRequest(BaseModel):
    kind: Literal["topup", "subscription"]
    kisa: int | None = Field(default=None, ge=1, le=100)
    language: Literal["ru", "en"] = "en"


@router.post("/checkout")
async def create_checkout(payload: CheckoutRequest,
                          user: User = Depends(get_current_user),
                          session: AsyncSession = Depends(get_session)):
    public = enabled()
    if not public and not (test_admin_enabled(user) and payload.kind == "topup"):
        raise HTTPException(503, "Payments are not enabled for this account")
    if payload.kind == "topup":
        if payload.kisa not in TOPUP_PACKAGES:
            raise HTTPException(422, "Unsupported Kisa package")
        amount, offer, credits = payload.kisa, TOPUP_OFFER, payload.kisa
    else:
        if payload.kisa is not None:
            raise HTTPException(422, "Subscription cannot contain Kisa amount")
        # Never buy a second recurring subscription from this button if an
        # earlier active subscription is already attached to this account.
        existing = (await session.execute(
            select(LavaMembership).where(
                LavaMembership.user_id == user.id,
                LavaMembership.status.in_(("active", "cancelled")),
                LavaMembership.valid_until > datetime.now(timezone.utc),
            ).limit(1)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(409, "An active Gardener+ membership already exists")
        pending = (await session.execute(
            select(LavaOrder).where(
                LavaOrder.user_id == user.id,
                LavaOrder.kind == "subscription",
                LavaOrder.status.in_(("creating", "pending")),
                LavaOrder.created_at > datetime.now(timezone.utc) - timedelta(hours=2),
            ).limit(1)
        )).scalar_one_or_none()
        if pending:
            raise HTTPException(409, "A Gardener+ checkout is already pending")
        amount, offer, credits = MONTHLY_PRICE_USD, SUBSCRIPTION_OFFER, 0

    order = LavaOrder(
        id=str(uuid4()), user_id=user.id, kind=payload.kind,
        kisa_amount=credits, amount=amount, currency="USD",
        offer_id=offer, status="creating",
    )
    session.add(order)
    await session.commit()
    try:
        invoice, checkout_url = await create_lava_invoice(
            email=user.email, offer_id=offer, kind=payload.kind, amount=amount,
            buyer_language=payload.language.upper())
    except LavaBuyerEmailRejected:
        order.status = "creation_failed"
        order.updated_at = datetime.now(timezone.utc)
        await session.commit()
        raise HTTPException(400, detail="lava_buyer_email_rejected")
    except Exception:
        order.status = "creation_failed"
        order.updated_at = datetime.now(timezone.utc)
        await session.commit()
        raise HTTPException(502, "Payment provider is unavailable")
    order.provider_invoice_id = invoice
    order.checkout_url = checkout_url
    order.status = "pending"
    order.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return {"checkout_url": checkout_url, "invoice_id": invoice, "status": "pending"}


@router.get("/status")
async def order_status(invoice_id: str, user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_session)):
    order = (await session.execute(
        select(LavaOrder).where(
            LavaOrder.provider_invoice_id == invoice_id,
            LavaOrder.user_id == user.id,
        )
    )).scalar_one_or_none()
    if order is None:
        raise HTTPException(404, "Payment not found")
    if order.status == "pending":
        try:
            await reconcile_invoice_status(session, invoice_id)
        except (RuntimeError, ValueError):
            # Report pending rather than trusting browser's ?status=success.
            await session.rollback()
    await session.refresh(order)
    return {"invoice_id": invoice_id, "status": order.status,
            "kind": order.kind, "kisa": order.kisa_amount}


@router.get("/membership")
async def membership_status(user: User = Depends(get_current_user),
                            session: AsyncSession = Depends(get_session)):
    records = (await session.execute(
        select(LavaMembership).where(LavaMembership.user_id == user.id)
        .order_by(LavaMembership.cycle_started_at.desc()).limit(1)
    )).scalars().all()
    if not records:
        return {"active": False, "remaining_entries": 0}
    m = records[0]
    # Use an explicit timezone-aware comparison, independent of DB driver.
    end = m.valid_until.replace(tzinfo=timezone.utc) if m.valid_until.tzinfo is None else m.valid_until
    return {"active": m.status in ("active", "cancelled") and end > datetime.now(timezone.utc),
            "remaining_entries": m.remaining_entries,
            "valid_until": end.isoformat(), "status": m.status}

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
    # The signed webhook is a notification, NOT payment proof. Verify the
    # invoice status, buyer and charged amount with Lava.top before granting.
    processed = False
    if event_type in ("payment.success", "subscription.recurring.payment.success") and invoice_id:
        try:
            outcome = await apply_verified_invoice(session, invoice_id)
            processed = outcome in ("granted", "granted_renewal", "already_granted")
            event = await session.get(LavaWebhookEvent, event_key)
            if event:
                event.status = "processed" if processed else outcome
                await session.commit()
        except (RuntimeError, ValueError):
            await session.rollback()
            # Lava.top will retry later if its verification API was unavailable.
            raise HTTPException(503, detail="Provider verification pending")
    elif event_type in ("payment.failed", "subscription.recurring.payment.failed") and invoice_id:
        try:
            outcome = await reconcile_invoice_status(session, invoice_id)
            processed = outcome in ("confirmed_failed", "already_granted")
            event = await session.get(LavaWebhookEvent, event_key)
            if event:
                event.status = "processed" if processed else outcome
                await session.commit()
        except (RuntimeError, ValueError):
            await session.rollback()
            raise HTTPException(503, detail="Provider verification pending")
    elif event_type in ("refund.success", "chargeback.initiated"):
        # Reconciliation required before altering credits. Never trust a refund
        # payload alone to choose a customer or subtract arbitrary Kisa.
        event = await session.get(LavaWebhookEvent, event_key)
        if event:
            event.status = "needs_manual_reconciliation"
            await session.commit()
    return {"received": True, "duplicate": duplicate, "processed": processed}
