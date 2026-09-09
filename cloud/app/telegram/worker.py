from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from html import escape
import logging
import secrets

from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal, create_tables, engine
from ..models import StarPayment, TelegramUser, WalletAccount, WalletTransaction
from .bot import TelegramBotAPI
from .i18n import language_for, t


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()

PACKAGES = {10: 100, 50: 550, 100: 1200, 250: 3250}


def main_keyboard(lang: str) -> dict:
    return {"inline_keyboard": [
        [
            {"text": t(lang, "menu_plants"), "callback_data": "menu:plants"},
            {"text": t(lang, "menu_garden"), "callback_data": "menu:garden"},
        ],
        [
            {"text": t(lang, "menu_community"), "callback_data": "menu:community"},
            {"text": t(lang, "menu_wallet"), "callback_data": "menu:wallet"},
        ],
        [{"text": t(lang, "menu_profile"), "callback_data": "menu:profile"}],
    ]}


def back_keyboard(lang: str) -> dict:
    return {"inline_keyboard": [[{"text": t(lang, "back_home"), "callback_data": "menu:home"}]]}


def terms_keyboard(lang: str, *, wallet_back: bool = True) -> dict:
    rows = [[{"text": t(lang, "accept"), "callback_data": "terms:accept"}]]
    if wallet_back:
        rows.append([{"text": t(lang, "back"), "callback_data": "menu:wallet"}])
    return {"inline_keyboard": rows}


async def get_or_create_user(tg: dict) -> tuple[TelegramUser, WalletAccount]:
    telegram_id = int(tg["id"])
    async with SessionLocal() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = TelegramUser(
                telegram_user_id=telegram_id,
                username=tg.get("username"),
                first_name=tg.get("first_name"),
                last_name=tg.get("last_name"),
                language_code=tg.get("language_code"),
            )
            session.add(user)
            await session.flush()
            wallet = WalletAccount(user_id=user.id, balance=0)
            session.add(wallet)
        else:
            user.username = tg.get("username")
            user.first_name = tg.get("first_name")
            user.last_name = tg.get("last_name")
            user.language_code = tg.get("language_code")
            user.updated_at = datetime.now(timezone.utc)
            result = await session.execute(
                select(WalletAccount).where(WalletAccount.user_id == user.id)
            )
            wallet = result.scalar_one_or_none()
            if wallet is None:
                wallet = WalletAccount(user_id=user.id, balance=0)
                session.add(wallet)
        await session.commit()
        return user, wallet


async def wallet_for_update(session, user_id: int) -> WalletAccount:
    result = await session.execute(
        select(WalletAccount).where(WalletAccount.user_id == user_id).with_for_update()
    )
    return result.scalar_one()


def invoice_payload(tg_id: int, stars: int, kisa: int) -> str:
    return f"kisa:{tg_id}:{stars}:{kisa}:{secrets.token_hex(6)}"


def parse_payload(payload: str):
    parts = payload.split(":")
    if len(parts) != 5 or parts[0] != "kisa":
        return None
    try:
        return int(parts[1]), int(parts[2]), int(parts[3])
    except ValueError:
        return None


async def show_home(bot: TelegramBotAPI, chat_id: int, tg: dict) -> None:
    lang = language_for(tg)
    user, wallet = await get_or_create_user(tg)
    await bot.send_message(
        chat_id,
        t(
            lang,
            "home",
            name=escape(user.first_name or "KisaMore"),
            balance=wallet.balance,
        ),
        reply_markup=main_keyboard(lang),
    )


async def show_wallet(bot: TelegramBotAPI, chat_id: int, tg: dict) -> None:
    lang = language_for(tg)
    user, wallet = await get_or_create_user(tg)
    rows = []
    if user.terms_accepted_at:
        for stars, kisa in PACKAGES.items():
            rows.append([
                {
                    "text": f"⭐ {stars} → 🪙 {kisa} Kisa",
                    "callback_data": f"wallet:buy:{stars}",
                }
            ])
        note = t(lang, "wallet_choose")
    else:
        rows.append([{"text": t(lang, "read_terms"), "callback_data": "terms:show"}])
        note = t(lang, "wallet_terms_required")
    rows.append([{"text": t(lang, "back_home"), "callback_data": "menu:home"}])
    await bot.send_message(
        chat_id,
        f"{t(lang, 'wallet_title')}\n\n{t(lang, 'balance', balance=wallet.balance)}\n\n{note}",
        reply_markup={"inline_keyboard": rows},
    )


async def show_profile(bot: TelegramBotAPI, chat_id: int, tg: dict) -> None:
    lang = language_for(tg)
    user, wallet = await get_or_create_user(tg)
    username = f"@{escape(user.username)}" if user.username else "—"
    await bot.send_message(
        chat_id,
        t(
            lang,
            "profile",
            name=escape(user.first_name or "—"),
            username=username,
            balance=wallet.balance,
        ),
        reply_markup=back_keyboard(lang),
    )


async def credit_payment(tg: dict, payment: dict) -> tuple[bool, int, int]:
    user, _ = await get_or_create_user(tg)
    parsed = parse_payload(str(payment.get("invoice_payload", "")))
    if parsed is None:
        raise ValueError("Invalid invoice payload")
    tg_id, stars, kisa = parsed
    if (
        tg_id != int(tg["id"])
        or payment.get("currency") != "XTR"
        or int(payment.get("total_amount", -1)) != stars
        or PACKAGES.get(stars) != kisa
    ):
        raise ValueError("Invalid payment parameters")
    charge_id = str(payment["telegram_payment_charge_id"])
    async with SessionLocal() as session:
        existing = await session.execute(
            select(StarPayment).where(StarPayment.telegram_payment_charge_id == charge_id)
        )
        if existing.scalar_one_or_none() is not None:
            wallet = await wallet_for_update(session, user.id)
            return False, wallet.balance, kisa
        wallet = await wallet_for_update(session, user.id)
        wallet.balance += kisa
        session.add(
            StarPayment(
                user_id=user.id,
                telegram_payment_charge_id=charge_id,
                provider_payment_charge_id=payment.get("provider_payment_charge_id") or None,
                invoice_payload=str(payment["invoice_payload"]),
                stars_amount=stars,
                kisa_amount=kisa,
                status="paid",
            )
        )
        session.add(
            WalletTransaction(
                user_id=user.id,
                amount=kisa,
                kind="stars_purchase",
                reference_type="telegram_payment",
                reference_id=charge_id,
                details={"stars": stars, "currency": "XTR"},
            )
        )
        await session.commit()
        return True, wallet.balance, kisa


async def handle_message(bot: TelegramBotAPI, message: dict) -> None:
    tg = message.get("from")
    chat_id = (message.get("chat") or {}).get("id")
    if tg is None or chat_id is None:
        return
    lang = language_for(tg)

    if message.get("successful_payment"):
        try:
            credited, balance, kisa = await credit_payment(tg, message["successful_payment"])
            if credited:
                await bot.send_message(
                    chat_id,
                    t(lang, "payment_received", kisa=kisa, balance=balance),
                    reply_markup=main_keyboard(lang),
                )
        except Exception:
            logger.exception("Failed to credit Stars payment")
            await bot.send_message(chat_id, t(lang, "payment_processing_error"))
        return

    text = (message.get("text") or "").strip()
    command = text.split(maxsplit=1)[0].split("@", 1)[0].lower()
    if command in {"/start", "/menu"}:
        await show_home(bot, chat_id, tg)
    elif command == "/wallet":
        await show_wallet(bot, chat_id, tg)
    elif command == "/profile":
        await show_profile(bot, chat_id, tg)
    elif command == "/plants":
        await get_or_create_user(tg)
        await bot.send_message(chat_id, t(lang, "plants"), reply_markup=back_keyboard(lang))
    elif command == "/garden":
        await get_or_create_user(tg)
        await bot.send_message(chat_id, t(lang, "garden"), reply_markup=back_keyboard(lang))
    elif command == "/terms":
        await get_or_create_user(tg)
        await bot.send_message(
            chat_id,
            t(lang, "terms"),
            reply_markup=terms_keyboard(lang),
        )
    elif command in {"/paysupport", "/support"}:
        contact = (
            escape(settings.telegram_support_contact)
            if settings.telegram_support_contact
            else t(lang, "support_not_configured")
        )
        await bot.send_message(chat_id, f"{t(lang, 'payment_support_title')}\n\n{contact}")
    elif command == "/help":
        await get_or_create_user(tg)
        await bot.send_message(chat_id, t(lang, "help"), reply_markup=back_keyboard(lang))
    else:
        await show_home(bot, chat_id, tg)


async def handle_callback(bot: TelegramBotAPI, query: dict) -> None:
    qid = query.get("id")
    tg = query.get("from")
    chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
    data = str(query.get("data") or "")
    if not qid or tg is None or chat_id is None:
        return
    lang = language_for(tg)
    await bot.answer_callback_query(qid)

    if data == "menu:home":
        await show_home(bot, chat_id, tg)
    elif data == "menu:wallet":
        await show_wallet(bot, chat_id, tg)
    elif data == "menu:profile":
        await show_profile(bot, chat_id, tg)
    elif data == "menu:plants":
        await get_or_create_user(tg)
        await bot.send_message(chat_id, t(lang, "plants"), reply_markup=back_keyboard(lang))
    elif data == "menu:garden":
        await get_or_create_user(tg)
        await bot.send_message(chat_id, t(lang, "garden"), reply_markup=back_keyboard(lang))
    elif data == "menu:community":
        await get_or_create_user(tg)
        await bot.send_message(chat_id, t(lang, "community"), reply_markup=back_keyboard(lang))
    elif data == "terms:show":
        await get_or_create_user(tg)
        await bot.send_message(
            chat_id,
            t(lang, "terms"),
            reply_markup=terms_keyboard(lang),
        )
    elif data == "terms:accept":
        user, _ = await get_or_create_user(tg)
        async with SessionLocal() as session:
            result = await session.execute(
                select(TelegramUser).where(TelegramUser.id == user.id)
            )
            db_user = result.scalar_one()
            if db_user.terms_accepted_at is None:
                db_user.terms_accepted_at = datetime.now(timezone.utc)
                await session.commit()
        await bot.send_message(chat_id, t(lang, "terms_accepted"))
        await show_wallet(bot, chat_id, tg)
    elif data.startswith("wallet:buy:"):
        user, _ = await get_or_create_user(tg)
        if not user.terms_accepted_at:
            await bot.send_message(
                chat_id,
                t(lang, "terms"),
                reply_markup=terms_keyboard(lang, wallet_back=False),
            )
            return
        try:
            stars = int(data.rsplit(":", 1)[-1])
        except ValueError:
            return
        kisa = PACKAGES.get(stars)
        if kisa is None:
            return
        await bot.send_invoice(
            chat_id,
            title=f"{kisa} Kisa",
            description=t(lang, "invoice_description", kisa=kisa),
            payload=invoice_payload(int(tg["id"]), stars, kisa),
            stars=stars,
        )


async def handle_pre_checkout(bot: TelegramBotAPI, query: dict) -> None:
    qid = query.get("id")
    tg = query.get("from")
    parsed = parse_payload(str(query.get("invoice_payload") or ""))
    valid = False
    lang = language_for(tg)
    if qid and tg and parsed:
        user, _ = await get_or_create_user(tg)
        tg_id, stars, kisa = parsed
        valid = bool(
            user.terms_accepted_at
            and tg_id == int(tg["id"])
            and query.get("currency") == "XTR"
            and int(query.get("total_amount", -1)) == stars
            and PACKAGES.get(stars) == kisa
        )
    if qid:
        await bot.answer_pre_checkout_query(
            qid,
            ok=valid,
            error_message=None if valid else t(lang, "precheckout_error"),
        )


async def handle_update(bot: TelegramBotAPI, update: dict) -> None:
    if "pre_checkout_query" in update:
        await handle_pre_checkout(bot, update["pre_checkout_query"])
    elif "callback_query" in update:
        await handle_callback(bot, update["callback_query"])
    elif "message" in update:
        await handle_message(bot, update["message"])


async def run() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("KISAMORE_TELEGRAM_BOT_TOKEN is not configured")
    await create_tables()
    bot = TelegramBotAPI(settings.telegram_bot_token)
    await bot.prepare_long_polling()
    logger.info("KisaMore Telegram bot started: @%s", settings.telegram_bot_username)
    offset = None
    try:
        while True:
            try:
                for update in await bot.get_updates(offset=offset, timeout_seconds=30):
                    update_id = int(update["update_id"])
                    try:
                        await handle_update(bot, update)
                    except Exception:
                        logger.exception("Failed to process Telegram update %s", update_id)
                    offset = update_id + 1
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telegram polling failed; retrying")
                await asyncio.sleep(3)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
