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


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()

PACKAGES = {10: 100, 50: 550, 100: 1200, 250: 3250}

TERMS_TEXT = (
    "<b>Условия KisaMore (beta)</b>\n\n"
    "Kisa — внутренние виртуальные баллы KisaMore. Они не являются криптовалютой, "
    "не имеют денежной стоимости вне KisaMore, не выводятся в деньги и не переводятся между пользователями.\n\n"
    "Kisa можно получать внутри сервиса и покупать за Telegram Stars. Баллы используются "
    "для цифровых функций KisaMore и в дальнейшем для доступа к услугам выращивания.\n\n"
    "Нажимая «Принимаю», вы подтверждаете согласие с этими условиями."
)


def main_keyboard() -> dict:
    return {"inline_keyboard": [
        [{"text": "🌱 Растения", "callback_data": "menu:plants"}, {"text": "🪴 Мой сад", "callback_data": "menu:garden"}],
        [{"text": "💬 Сообщество", "callback_data": "menu:community"}, {"text": "🪙 Кошелёк", "callback_data": "menu:wallet"}],
        [{"text": "👤 Профиль", "callback_data": "menu:profile"}],
    ]}


def back_keyboard() -> dict:
    return {"inline_keyboard": [[{"text": "◀️ Главное меню", "callback_data": "menu:home"}]]}


async def get_or_create_user(tg: dict) -> tuple[TelegramUser, WalletAccount]:
    telegram_id = int(tg["id"])
    async with SessionLocal() as session:
        result = await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
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
            result = await session.execute(select(WalletAccount).where(WalletAccount.user_id == user.id))
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
    user, wallet = await get_or_create_user(tg)
    await bot.send_message(
        chat_id,
        f"🌱 <b>KisaMore</b>\n\nПривет, {escape(user.first_name or 'друг')}!\n\n"
        "Наблюдайте за настоящими растениями, следите за ростом, общайтесь и позже арендуйте свой контейнер.\n\n"
        f"🪙 Баланс: <b>{wallet.balance} Kisa</b>",
        reply_markup=main_keyboard(),
    )


async def show_wallet(bot: TelegramBotAPI, chat_id: int, tg: dict) -> None:
    user, wallet = await get_or_create_user(tg)
    rows = []
    if user.terms_accepted_at:
        for stars, kisa in PACKAGES.items():
            rows.append([{"text": f"⭐ {stars} → 🪙 {kisa} Kisa", "callback_data": f"wallet:buy:{stars}"}])
        note = "Выберите пакет для покупки через Telegram Stars."
    else:
        rows.append([{"text": "📄 Прочитать условия", "callback_data": "terms:show"}])
        note = "Перед первой покупкой нужно принять условия KisaMore."
    rows.append([{"text": "◀️ Главное меню", "callback_data": "menu:home"}])
    await bot.send_message(chat_id, f"🪙 <b>Кошелёк Kisa</b>\n\nБаланс: <b>{wallet.balance} Kisa</b>\n\n{note}", reply_markup={"inline_keyboard": rows})


async def show_profile(bot: TelegramBotAPI, chat_id: int, tg: dict) -> None:
    user, wallet = await get_or_create_user(tg)
    username = f"@{escape(user.username)}" if user.username else "—"
    await bot.send_message(
        chat_id,
        f"👤 <b>Профиль</b>\n\nИмя: {escape(user.first_name or '—')}\nTelegram: {username}\n"
        f"🪙 Баланс: <b>{wallet.balance} Kisa</b>\n\n"
        "Здесь позже появятся выращенные растения, достижения, подписчики и награды.",
        reply_markup=back_keyboard(),
    )


async def credit_payment(tg: dict, payment: dict) -> tuple[bool, int, int]:
    user, _ = await get_or_create_user(tg)
    parsed = parse_payload(str(payment.get("invoice_payload", "")))
    if parsed is None:
        raise ValueError("Invalid invoice payload")
    tg_id, stars, kisa = parsed
    if tg_id != int(tg["id"]) or payment.get("currency") != "XTR" or int(payment.get("total_amount", -1)) != stars or PACKAGES.get(stars) != kisa:
        raise ValueError("Invalid payment parameters")
    charge_id = str(payment["telegram_payment_charge_id"])
    async with SessionLocal() as session:
        existing = await session.execute(select(StarPayment).where(StarPayment.telegram_payment_charge_id == charge_id))
        if existing.scalar_one_or_none() is not None:
            wallet = await wallet_for_update(session, user.id)
            return False, wallet.balance, kisa
        wallet = await wallet_for_update(session, user.id)
        wallet.balance += kisa
        session.add(StarPayment(
            user_id=user.id,
            telegram_payment_charge_id=charge_id,
            provider_payment_charge_id=payment.get("provider_payment_charge_id") or None,
            invoice_payload=str(payment["invoice_payload"]),
            stars_amount=stars,
            kisa_amount=kisa,
            status="paid",
        ))
        session.add(WalletTransaction(
            user_id=user.id,
            amount=kisa,
            kind="stars_purchase",
            reference_type="telegram_payment",
            reference_id=charge_id,
            details={"stars": stars, "currency": "XTR"},
        ))
        await session.commit()
        return True, wallet.balance, kisa


async def handle_message(bot: TelegramBotAPI, message: dict) -> None:
    tg = message.get("from")
    chat_id = (message.get("chat") or {}).get("id")
    if tg is None or chat_id is None:
        return
    if message.get("successful_payment"):
        try:
            credited, balance, kisa = await credit_payment(tg, message["successful_payment"])
            if credited:
                await bot.send_message(chat_id, f"✅ <b>Оплата получена</b>\n\nНачислено: <b>{kisa} Kisa</b>\nНовый баланс: <b>{balance} Kisa</b>", reply_markup=main_keyboard())
        except Exception:
            logger.exception("Failed to credit Stars payment")
            await bot.send_message(chat_id, "⚠️ Платёж получен, но не обработан автоматически. Используйте /paysupport.")
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
        await bot.send_message(chat_id, "🌱 <b>Текущие растения</b>\n\nСледующим этапом подключим сюда реальные растения, последние фото и таймлапсы из VPS-БД.", reply_markup=back_keyboard())
    elif command == "/garden":
        await get_or_create_user(tg)
        await bot.send_message(chat_id, "🪴 <b>Мой сад</b>\n\nЗдесь будут арендованные контейнеры и ваши растения.", reply_markup=back_keyboard())
    elif command == "/terms":
        await get_or_create_user(tg)
        await bot.send_message(chat_id, TERMS_TEXT, reply_markup={"inline_keyboard": [[{"text": "✅ Принимаю", "callback_data": "terms:accept"}], [{"text": "◀️ Назад", "callback_data": "menu:wallet"}]]})
    elif command in {"/paysupport", "/support"}:
        contact = escape(settings.telegram_support_contact) if settings.telegram_support_contact else "контакт пока не настроен"
        await bot.send_message(chat_id, f"💳 <b>Поддержка по платежам</b>\n\n{contact}")
    else:
        await show_home(bot, chat_id, tg)


async def handle_callback(bot: TelegramBotAPI, query: dict) -> None:
    qid = query.get("id")
    tg = query.get("from")
    chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
    data = str(query.get("data") or "")
    if not qid or tg is None or chat_id is None:
        return
    await bot.answer_callback_query(qid)

    if data == "menu:home":
        await show_home(bot, chat_id, tg)
    elif data == "menu:wallet":
        await show_wallet(bot, chat_id, tg)
    elif data == "menu:profile":
        await show_profile(bot, chat_id, tg)
    elif data == "menu:plants":
        await bot.send_message(chat_id, "🌱 <b>Текущие растения</b>\n\nРеальная лента растений будет подключена следующим этапом.", reply_markup=back_keyboard())
    elif data == "menu:garden":
        await bot.send_message(chat_id, "🪴 <b>Мой сад</b>\n\nРаздел аренды контейнеров будет подключён следующим этапом.", reply_markup=back_keyboard())
    elif data == "menu:community":
        await bot.send_message(chat_id, "💬 <b>Сообщество</b>\n\nЗдесь будут комментарии, рейтинги, соревнования и Plant Battles.", reply_markup=back_keyboard())
    elif data == "terms:show":
        await bot.send_message(chat_id, TERMS_TEXT, reply_markup={"inline_keyboard": [[{"text": "✅ Принимаю", "callback_data": "terms:accept"}], [{"text": "◀️ Назад", "callback_data": "menu:wallet"}]]})
    elif data == "terms:accept":
        user, _ = await get_or_create_user(tg)
        async with SessionLocal() as session:
            result = await session.execute(select(TelegramUser).where(TelegramUser.id == user.id))
            db_user = result.scalar_one()
            if db_user.terms_accepted_at is None:
                db_user.terms_accepted_at = datetime.now(timezone.utc)
                await session.commit()
        await bot.send_message(chat_id, "✅ Условия приняты.")
        await show_wallet(bot, chat_id, tg)
    elif data.startswith("wallet:buy:"):
        user, _ = await get_or_create_user(tg)
        if not user.terms_accepted_at:
            await bot.send_message(chat_id, TERMS_TEXT, reply_markup={"inline_keyboard": [[{"text": "✅ Принимаю", "callback_data": "terms:accept"}]]})
            return
        try:
            stars = int(data.rsplit(":", 1)[-1])
        except ValueError:
            return
        kisa = PACKAGES.get(stars)
        if kisa is None:
            return
        await bot.send_invoice(chat_id, title=f"{kisa} Kisa", description=f"Пополнение внутреннего баланса KisaMore на {kisa} Kisa.", payload=invoice_payload(int(tg["id"]), stars, kisa), stars=stars)


async def handle_pre_checkout(bot: TelegramBotAPI, query: dict) -> None:
    qid = query.get("id")
    tg = query.get("from")
    parsed = parse_payload(str(query.get("invoice_payload") or ""))
    valid = False
    if qid and tg and parsed:
        user, _ = await get_or_create_user(tg)
        tg_id, stars, kisa = parsed
        valid = bool(user.terms_accepted_at and tg_id == int(tg["id"]) and query.get("currency") == "XTR" and int(query.get("total_amount", -1)) == stars and PACKAGES.get(stars) == kisa)
    if qid:
        await bot.answer_pre_checkout_query(qid, ok=valid, error_message=None if valid else "Не удалось проверить заказ. Создайте новый счёт в кошельке KisaMore.")


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
