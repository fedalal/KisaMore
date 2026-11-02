"""Lava.top invoice client and server-verified, idempotent order fulfillment."""
from __future__ import annotations

import calendar
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import os
from urllib.parse import urlparse
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .lava_payments_models import LavaGrantedInvoice, LavaMembership, LavaOrder
from .models import User
from .site_wallet import locked_wallet, record_wallet_change

class LavaBuyerEmailRejected(RuntimeError):
    """Provider refused this buyer email; do not retry with the seller account."""
    pass

LAVA_API = "https://gate.lava.top"
TOPUP_OFFER = "5bdc8f1f-a2a9-43eb-8ec3-4783aeb3cc04"
SUBSCRIPTION_OFFER = "f0af1395-e62d-4c7b-8d97-45b3d2032970"
TOPUP_PACKAGES = (10, 20, 50, 100)
MONTHLY_PRICE_USD = 30

def enabled() -> bool:
    return (os.getenv("KISAMORE_LAVA_PAYMENTS_ENABLED", "").lower() in ("true", "yes", "1")
            and bool(os.getenv("KISAMORE_LAVA_API_KEY", "")))

def _headers() -> dict:
    token = os.getenv("KISAMORE_LAVA_API_KEY", "")
    if not token:
        raise RuntimeError("Lava.top API credentials unavailable")
    return {"X-Api-Key": token, "Accept": "application/json"}

def _url_allowed(value: str) -> bool:
    try:
        url = urlparse(value)
        return url.scheme == "https" and (url.hostname == "lava.top" or (url.hostname or "").endswith(".lava.top")) and not url.username and not url.password
    except (ValueError, TypeError):
        return False

def _uuid(value: str) -> str:
    return str(UUID(str(value)))

async def create_lava_invoice(*, email: str, offer_id: str, kind: str, amount: int) -> tuple[str, str]:
    body = {
        "email": email,
        "offerId": offer_id,
        "currency": "USD",
        "successful_return_url": "https://kisamore.farm/wallet?payment=return",
        "failure_return_url": "https://kisamore.farm/wallet?payment=failed",
        "cancel_return_url": "https://kisamore.farm/wallet?payment=cancelled",
    }
    if kind == "topup":
        body["amount"] = amount
    else:
        body["periodicity"] = "MONTHLY"
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        response = await client.post(LAVA_API + "/api/v3/invoice", json=body,
                                     headers={**_headers(), "Content-Type": "application/json"})
    if response.status_code != 201:
        # Only expose a recognized, non-sensitive error class to our UI.
        # Never return raw provider responses containing customer data.
        if response.status_code == 400:
            try:
                reason = response.json().get("error")
            except (ValueError, AttributeError):
                reason = None
            if isinstance(reason, str) and reason.strip().casefold() == "incorrect email to purchase":
                raise LavaBuyerEmailRejected("Lava.top refused the purchaser email")
        raise RuntimeError("Lava.top rejected invoice creation: " + str(response.status_code))
    data = response.json()
    invoice_id = _uuid(data.get("id"))
    checkout = data.get("paymentUrl")
    if not isinstance(checkout, str) or not _url_allowed(checkout):
        raise RuntimeError("Lava.top did not return a supported secure checkout URL")
    return invoice_id, checkout

async def get_invoice(invoice_id: str) -> dict:
    invoice_id = _uuid(invoice_id)
    async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
        response = await client.get(LAVA_API + "/api/v2/invoices/" + invoice_id, headers=_headers())
    if response.status_code != 200:
        raise RuntimeError("Lava.top invoice verification failed: " + str(response.status_code))
    data = response.json()
    if not isinstance(data, dict) or str(data.get("id", "")).lower() != invoice_id:
        raise RuntimeError("Lava.top returned a mismatched invoice")
    return data

async def reconcile_invoice_status(session: AsyncSession, invoice_id: str) -> str:
    """Refresh a known order from the provider, including cancelled/failed invoices.

    Never credit from user return URLs or webhook payloads. Completed invoices
    use the existing verified, exactly-once fulfillment mechanism.
    """
    invoice_id = _uuid(invoice_id)
    order = (await session.execute(
        select(LavaOrder).where(LavaOrder.provider_invoice_id == invoice_id)
    )).scalar_one_or_none()
    if order is None:
        return "unmatched_invoice"
    if order.status == "paid":
        return "already_granted"
    remote = await get_invoice(invoice_id)
    if remote.get("status") == "FAILED":
        order.status = "failed"
        order.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return "confirmed_failed"
    if remote.get("status") == "COMPLETED":
        return await apply_verified_invoice(session, invoice_id)
    return "pending"


def _money_matches(invoice: dict, expected: int, currency: str) -> bool:
    receipt = invoice.get("receipt")
    if not isinstance(receipt, dict) or receipt.get("currency") != currency:
        return False
    try:
        return Decimal(str(receipt["amount"])) == Decimal(expected)
    except (InvalidOperation, KeyError, TypeError):
        return False

def _email_matches(invoice: dict, user: User) -> bool:
    buyer = invoice.get("buyer") or {}
    return isinstance(buyer, dict) and str(buyer.get("email", "")).strip().casefold() == user.email.casefold()

def _plus_month(dt: datetime) -> datetime:
    year = dt.year + dt.month // 12
    month = dt.month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)

def _expiry(invoice: dict) -> datetime:
    details = invoice.get("subscriptionDetails") or {}
    value = details.get("expiredAt") if isinstance(details, dict) else None
    if value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo:
                return dt.astimezone(timezone.utc)
        except (TypeError, ValueError):
            pass
    return _plus_month(datetime.now(timezone.utc))

def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

async def apply_verified_invoice(session: AsyncSession, invoice_id: str) -> str:
    """Verify against Lava API and credit atomically; never trust webhook/URL status."""
    invoice_id = _uuid(invoice_id)
    remote = await get_invoice(invoice_id)
    if remote.get("status") != "COMPLETED":
        return "not_completed"
    now = datetime.now(timezone.utc)
    order = (await session.execute(
        select(LavaOrder).where(LavaOrder.provider_invoice_id == invoice_id)
    )).scalar_one_or_none()
    invoice_type = remote.get("type")

    if order is not None:
        user = await session.get(User, order.user_id, with_for_update=True)
        if user is None or not _email_matches(remote, user):
            raise ValueError("Lava invoice buyer does not match order owner")
        if not _money_matches(remote, order.amount, order.currency):
            raise ValueError("Lava invoice amount mismatch")
        if order.kind == "topup" and (order.offer_id != TOPUP_OFFER or invoice_type != "INVOICE"):
            raise ValueError("Unexpected product invoice")
        if order.kind == "subscription" and (order.offer_id != SUBSCRIPTION_OFFER or invoice_type != "SUBSCRIPTION_FIRST_INVOICE"):
            raise ValueError("Unexpected subscription invoice")
        if await session.get(LavaGrantedInvoice, invoice_id):
            return "already_granted"
        session.add(LavaGrantedInvoice(invoice_id=invoice_id, order_id=order.id,
                                       user_id=user.id, kind=order.kind))
        await session.flush()
        if order.kind == "topup":
            wallet, telegram_user = await locked_wallet(session, user.id)
            wallet.balance += order.kisa_amount
            record_wallet_change(
                session, user_id=user.id, telegram_user=telegram_user,
                wallet=wallet, amount=order.kisa_amount, kind="lava_topup",
                reference_type="lava_invoice", reference_id=invoice_id,
                details={"currency": order.currency, "amount": order.amount},
            )
        else:
            session.add(LavaMembership(
                parent_invoice_id=invoice_id, user_id=user.id, remaining_entries=3,
                cycle_started_at=now, valid_until=_expiry(remote),
                last_invoice_id=invoice_id, status="active",
            ))
        order.status = "paid"
        order.updated_at = now
        await session.commit()
        return "granted"

    # Renewals create new invoice IDs, but must reference a known first payment.
    if invoice_type != "SUBSCRIPTION_RENEWAL":
        return "unmatched_invoice"
    parent = remote.get("parentInvoice") or {}
    parent_id = parent.get("id") if isinstance(parent, dict) else None
    if not parent_id:
        return "renewal_without_parent"
    parent_id = _uuid(parent_id)
    # Lock order must match battle joins: User first, then membership.
    membership = await session.get(LavaMembership, parent_id)
    if membership is None:
        return "unknown_membership"
    user = await session.get(User, membership.user_id, with_for_update=True)
    membership = await session.get(LavaMembership, parent_id, with_for_update=True, populate_existing=True)
    if user is None or membership is None or not _email_matches(remote, user) or not _money_matches(remote, MONTHLY_PRICE_USD, "USD"):
        raise ValueError("Subscription renewal mismatch")
    if await session.get(LavaGrantedInvoice, invoice_id):
        return "already_granted"
    session.add(LavaGrantedInvoice(invoice_id=invoice_id, order_id=None,
                                   user_id=user.id, kind="renewal"))
    await session.flush()
    membership.remaining_entries = 3
    membership.cycle_started_at = now
    membership.valid_until = _expiry(remote)
    membership.last_invoice_id = invoice_id
    membership.status = "active"
    membership.updated_at = now
    await session.commit()
    return "granted_renewal"
