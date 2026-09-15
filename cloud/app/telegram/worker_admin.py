from __future__ import annotations

import asyncio
from html import escape

from fastapi import HTTPException
from sqlalchemy import select

from ..admin_models import AdminAuditLog
from ..db import SessionLocal
from ..models import User
from ..rental_admin_api import RejectRentalIn, approve_rental_request, reject_rental_request
from . import admin_rental_notifier, new_user_notifier
from . import worker_seed_inventory as existing
from .models import (
    TelegramConversationState,
    TelegramUser,
    WalletAccount,
    WalletTransaction,
)


core = existing.core
_previous_handle_callback = core.handle_callback
_previous_handle_message = core.handle_message
_previous_follow_notification_loop = core.follow_notification_loop


async def _authorized_admin(tg: dict):
    user, _ = await core.get_or_create_user(tg)
    if not await admin_rental_notifier.is_telegram_admin(user.id):
        return user, None
    async with SessionLocal() as session:
        web_admin = (
            await session.execute(
                select(User)
                .where(User.role == "admin", User.is_active.is_(True))
                .order_by(User.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
    return user, web_admin


async def _show_pending(bot, chat_id: int) -> None:
    rows = await admin_rental_notifier.pending_requests(20)
    if not rows:
        await bot.send_message(chat_id, "✅ <b>Новых заявок на аренду нет.</b>")
        return
    await bot.send_message(
        chat_id,
        f"🛡 <b>Заявки на аренду: {len(rows)}</b>\n\n"
        "Ниже показаны заявки, которые ждут решения.",
    )
    for row in rows:
        text, keyboard = admin_rental_notifier.format_pending_request(row)
        await bot.send_message(chat_id, text, reply_markup=keyboard)


def _gift_amount_keyboard(target_user_id: int) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Ⓚ 10", "callback_data": f"adminuser:giftamt:{target_user_id}:10"},
                {"text": "Ⓚ 25", "callback_data": f"adminuser:giftamt:{target_user_id}:25"},
            ],
            [
                {"text": "Ⓚ 50", "callback_data": f"adminuser:giftamt:{target_user_id}:50"},
                {"text": "Ⓚ 100", "callback_data": f"adminuser:giftamt:{target_user_id}:100"},
            ],
            [
                {"text": "✍️ Другая сумма", "callback_data": f"adminuser:giftcustom:{target_user_id}"},
            ],
            [
                {"text": "↩️ Отмена", "callback_data": "adminuser:cancel"},
            ],
        ]
    }


async def _set_admin_state(
    admin_user_id: int,
    mode: str,
    target_user_id: int,
    *,
    payload: dict | None = None,
) -> None:
    async with SessionLocal() as session:
        state = (
            await session.execute(
                select(TelegramConversationState).where(
                    TelegramConversationState.user_id == admin_user_id
                )
            )
        ).scalar_one_or_none()
        if state is None:
            state = TelegramConversationState(
                user_id=admin_user_id,
                mode=mode,
                target_type="telegram_user",
                target_id=str(target_user_id),
                payload=payload or {},
            )
            session.add(state)
        else:
            state.mode = mode
            state.target_type = "telegram_user"
            state.target_id = str(target_user_id)
            state.payload = payload or {}
        await session.commit()


async def _clear_admin_state(admin_user_id: int) -> None:
    async with SessionLocal() as session:
        state = (
            await session.execute(
                select(TelegramConversationState).where(
                    TelegramConversationState.user_id == admin_user_id
                )
            )
        ).scalar_one_or_none()
        if state is not None and state.mode.startswith("admin_gift_"):
            await session.delete(state)
            await session.commit()


async def _admin_gift_state(admin_user_id: int):
    async with SessionLocal() as session:
        state = (
            await session.execute(
                select(TelegramConversationState).where(
                    TelegramConversationState.user_id == admin_user_id,
                    TelegramConversationState.mode.in_(("admin_gift_amount", "admin_gift_note")),
                )
            )
        ).scalar_one_or_none()
        if state is None:
            return None
        return {
            "mode": state.mode,
            "target_id": state.target_id,
            "payload": dict(state.payload or {}),
        }


async def _gift_user(
    *,
    target_user_id: int,
    amount: int,
    reason: str,
    admin_tg_user_id: int,
    web_admin: User,
) -> tuple[TelegramUser, int]:
    async with SessionLocal() as session:
        recipient = await session.get(TelegramUser, target_user_id)
        if recipient is None:
            raise ValueError("user_not_found")

        wallet = (
            await session.execute(
                select(WalletAccount)
                .where(WalletAccount.user_id == recipient.id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if wallet is None:
            wallet = WalletAccount(user_id=recipient.id, balance=0)
            session.add(wallet)
            await session.flush()

        wallet.balance += amount
        session.add(
            WalletTransaction(
                user_id=recipient.id,
                amount=amount,
                balance_after=wallet.balance,
                kind="admin_gift",
                reference_type="admin",
                reference_id=web_admin.id,
                details={"reason": reason, "admin_email": web_admin.email, "source": "telegram_admin"},
            )
        )
        session.add(
            AdminAuditLog(
                admin_user_id=web_admin.id,
                action="gift_kisa",
                target_type="telegram_user",
                target_id=str(recipient.id),
                details={
                    "amount": amount,
                    "reason": reason,
                    "balance_after": wallet.balance,
                    "source": "telegram_admin",
                },
            )
        )

        state = (
            await session.execute(
                select(TelegramConversationState).where(
                    TelegramConversationState.user_id == admin_tg_user_id
                )
            )
        ).scalar_one_or_none()
        if state is not None and state.mode.startswith("admin_gift_"):
            await session.delete(state)

        await session.commit()
        return recipient, int(wallet.balance)


async def _handle_admin_gift_message(bot, message: dict, tg: dict, chat_id: int) -> bool:
    admin_user, web_admin = await _authorized_admin(tg)
    if web_admin is None:
        return False

    state = await _admin_gift_state(admin_user.id)
    if state is None:
        return False

    text = (message.get("text") or "").strip()
    if text.lower().split("@", 1)[0] == "/cancel":
        await _clear_admin_state(admin_user.id)
        await bot.send_message(chat_id, "↩️ Подарок отменён.")
        return True

    try:
        target_user_id = int(state["target_id"] or 0)
    except (TypeError, ValueError):
        await _clear_admin_state(admin_user.id)
        return True

    if state["mode"] == "admin_gift_amount":
        try:
            amount = int(text.replace(" ", ""))
        except ValueError:
            amount = 0
        if amount < 1 or amount > 1_000_000:
            await bot.send_message(
                chat_id,
                "Введите сумму целым числом от 1 до 1 000 000 Kisa или /cancel.",
            )
            return True
        await _set_admin_state(
            admin_user.id,
            "admin_gift_note",
            target_user_id,
            payload={"amount": amount},
        )
        await bot.send_message(
            chat_id,
            f"🎁 Сумма: <b>Ⓚ {amount}</b>\n\n"
            "Теперь напишите сообщение, которое пользователь увидит вместе с подарком.\n"
            "Например: <i>Добро пожаловать в KisaMore!</i>\n\n"
            "Для отмены: /cancel",
        )
        return True

    amount = int(state["payload"].get("amount") or 0)
    if amount < 1:
        await _clear_admin_state(admin_user.id)
        return True
    if len(text) < 2 or len(text) > 300:
        await bot.send_message(
            chat_id,
            "Сообщение должно содержать от 2 до 300 символов. Попробуйте ещё раз или /cancel.",
        )
        return True

    try:
        recipient, balance = await _gift_user(
            target_user_id=target_user_id,
            amount=amount,
            reason=text,
            admin_tg_user_id=admin_user.id,
            web_admin=web_admin,
        )
    except ValueError:
        await _clear_admin_state(admin_user.id)
        await bot.send_message(chat_id, "⚠️ Пользователь больше не найден.")
        return True
    except Exception:
        core.logger.exception("Telegram admin quick gift failed for user %s", target_user_id)
        await bot.send_message(chat_id, "⚠️ Не удалось начислить подарок. Попробуйте ещё раз.")
        return True

    name = " ".join(v for v in (recipient.first_name, recipient.last_name) if v).strip()
    if not name:
        name = f"@{recipient.username}" if recipient.username else f"Telegram {recipient.telegram_user_id}"
    await bot.send_message(
        chat_id,
        f"✅ <b>Подарок отправлен</b>\n\n"
        f"Пользователь: <b>{escape(name)}</b>\n"
        f"Начислено: <b>Ⓚ {amount}</b>\n"
        f"Новый баланс: <b>Ⓚ {balance}</b>\n\n"
        "Пользователь получит сообщение с вашим текстом.",
    )
    return True


async def handle_message(bot, message: dict) -> None:
    tg = message.get("from")
    chat_id = (message.get("chat") or {}).get("id")
    if tg is not None and chat_id is not None:
        if await _handle_admin_gift_message(bot, message, tg, chat_id):
            return

    text = (message.get("text") or "").strip()
    command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text else ""
    if command != "/admin":
        await _previous_handle_message(bot, message)
        return

    if tg is None or chat_id is None:
        return
    _, web_admin = await _authorized_admin(tg)
    if web_admin is None:
        await bot.send_message(chat_id, "⛔ Команда доступна только администратору KisaMore.")
        return
    await _show_pending(bot, chat_id)


async def _handle_admin_user_callback(bot, query: dict) -> bool:
    data = str(query.get("data") or "")
    if not data.startswith("adminuser:"):
        return False

    qid = query.get("id")
    tg = query.get("from")
    chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
    if not qid or tg is None or chat_id is None:
        return True

    admin_user, web_admin = await _authorized_admin(tg)
    if web_admin is None:
        await bot.answer_callback_query(qid, text="Нет прав администратора", show_alert=True)
        return True

    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "cancel":
        await _clear_admin_state(admin_user.id)
        await bot.answer_callback_query(qid, text="Отменено")
        await bot.send_message(chat_id, "↩️ Подарок отменён.")
        return True

    if action == "gift" and len(parts) == 3:
        try:
            target_user_id = int(parts[2])
        except ValueError:
            await bot.answer_callback_query(qid)
            return True
        async with SessionLocal() as session:
            target = await session.get(TelegramUser, target_user_id)
        if target is None:
            await bot.answer_callback_query(qid, text="Пользователь не найден", show_alert=True)
            return True
        await bot.answer_callback_query(qid)
        name = " ".join(v for v in (target.first_name, target.last_name) if v).strip()
        if not name:
            name = f"@{target.username}" if target.username else f"Telegram {target.telegram_user_id}"
        await bot.send_message(
            chat_id,
            f"🎁 <b>Подарок пользователю {escape(name)}</b>\n\nВыберите сумму:",
            reply_markup=_gift_amount_keyboard(target_user_id),
        )
        return True

    if action == "giftcustom" and len(parts) == 3:
        try:
            target_user_id = int(parts[2])
        except ValueError:
            await bot.answer_callback_query(qid)
            return True
        await _set_admin_state(admin_user.id, "admin_gift_amount", target_user_id)
        await bot.answer_callback_query(qid)
        await bot.send_message(
            chat_id,
            "✍️ Введите количество Kisa целым числом от 1 до 1 000 000.\n\nДля отмены: /cancel",
        )
        return True

    if action == "giftamt" and len(parts) == 4:
        try:
            target_user_id = int(parts[2])
            amount = int(parts[3])
        except ValueError:
            await bot.answer_callback_query(qid)
            return True
        if amount < 1 or amount > 1_000_000:
            await bot.answer_callback_query(qid, text="Некорректная сумма", show_alert=True)
            return True
        await _set_admin_state(
            admin_user.id,
            "admin_gift_note",
            target_user_id,
            payload={"amount": amount},
        )
        await bot.answer_callback_query(qid)
        await bot.send_message(
            chat_id,
            f"🎁 Сумма: <b>Ⓚ {amount}</b>\n\n"
            "Напишите сообщение, которое пользователь увидит вместе с подарком.\n"
            "Например: <i>Добро пожаловать в KisaMore!</i>\n\n"
            "Для отмены: /cancel",
        )
        return True

    await bot.answer_callback_query(qid)
    return True


async def handle_callback(bot, query: dict) -> None:
    if await _handle_admin_user_callback(bot, query):
        return

    data = str(query.get("data") or "")
    if not data.startswith("adminrent:"):
        await _previous_handle_callback(bot, query)
        return

    qid = query.get("id")
    tg = query.get("from")
    chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
    if not qid or tg is None or chat_id is None:
        return

    _, web_admin = await _authorized_admin(tg)
    if web_admin is None:
        await bot.answer_callback_query(qid, text="Нет прав администратора", show_alert=True)
        return

    if data == "adminrent:list":
        await bot.answer_callback_query(qid)
        await _show_pending(bot, chat_id)
        return

    parts = data.split(":")
    if len(parts) != 3:
        await bot.answer_callback_query(qid)
        return
    action = parts[1]
    try:
        request_id = int(parts[2])
    except ValueError:
        await bot.answer_callback_query(qid)
        return

    if action == "reject":
        await bot.answer_callback_query(qid)
        await bot.send_message(
            chat_id,
            f"❌ <b>Отклонить заявку #{request_id}?</b>\n\n"
            "Если заявка была оплачена Kisa, сумма будет возвращена пользователю.",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "❌ Да, отклонить", "callback_data": f"adminrent:rejectconfirm:{request_id}"}],
                    [{"text": "↩️ Отмена", "callback_data": "adminrent:list"}],
                ]
            },
        )
        return

    if action not in ("approve", "rejectconfirm"):
        await bot.answer_callback_query(qid)
        return

    await bot.answer_callback_query(qid, text="Обрабатываю…")
    try:
        async with SessionLocal() as session:
            if action == "approve":
                result = await approve_rental_request(
                    request_id,
                    admin=web_admin,
                    session=session,
                )
                allocation_id = result.get("allocation_id") or "создано"
                await bot.send_message(
                    chat_id,
                    f"✅ <b>Заявка #{request_id} одобрена.</b>\n"
                    f"Назначение: {allocation_id}\n\n"
                    "Пользователь получит уведомление в Telegram.",
                )
            else:
                result = await reject_rental_request(
                    request_id,
                    RejectRentalIn(reason="Отклонено администратором через Telegram"),
                    admin=web_admin,
                    session=session,
                )
                refunded = int(result.get("refunded_kisa") or 0)
                refund_text = f"\nВозвращено пользователю: Ⓚ {refunded}." if refunded else ""
                await bot.send_message(
                    chat_id,
                    f"❌ <b>Заявка #{request_id} отклонена.</b>"
                    f"{refund_text}\n\nПользователь получит уведомление в Telegram.",
                )
    except HTTPException as exc:
        await bot.send_message(
            chat_id,
            f"⚠️ Не удалось обработать заявку #{request_id}: {core.escape(str(exc.detail)) if hasattr(core, 'escape') else str(exc.detail)}",
        )
    except Exception:
        core.logger.exception("Telegram admin rental action failed for request %s", request_id)
        await bot.send_message(chat_id, f"⚠️ Ошибка при обработке заявки #{request_id}.")


async def follow_notification_loop(bot) -> None:
    async def admin_alert_loop() -> None:
        while True:
            try:
                welcomed = await admin_rental_notifier.send_welcome_messages(bot)
                rental_sent, rental_failed = await admin_rental_notifier.send_pending_alerts(bot)
                new_discovered = await new_user_notifier.discover_new_users()
                new_sent, new_failed = await new_user_notifier.send_pending_alerts(bot)
                if welcomed or rental_sent or rental_failed or new_discovered or new_sent or new_failed:
                    core.logger.info(
                        "Telegram admin alert pass: welcomed=%s rental_sent=%s rental_failed=%s "
                        "new_discovered=%s new_sent=%s new_failed=%s",
                        welcomed,
                        rental_sent,
                        rental_failed,
                        new_discovered,
                        new_sent,
                        new_failed,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                core.logger.exception("Telegram admin alert pass failed")
            await asyncio.sleep(admin_rental_notifier.CHECK_SECONDS)

    await asyncio.gather(
        _previous_follow_notification_loop(bot),
        admin_alert_loop(),
    )


core.handle_message = handle_message
core.handle_callback = handle_callback
core.follow_notification_loop = follow_notification_loop


if __name__ == "__main__":
    asyncio.run(core.run())
