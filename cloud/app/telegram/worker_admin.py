from __future__ import annotations

import asyncio

from fastapi import HTTPException
from sqlalchemy import select

from ..db import SessionLocal
from ..models import User
from ..rental_admin_api import RejectRentalIn, approve_rental_request, reject_rental_request
from . import admin_rental_notifier
from . import worker_seed_inventory as existing


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


async def handle_message(bot, message: dict) -> None:
    text = (message.get("text") or "").strip()
    command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text else ""
    if command != "/admin":
        await _previous_handle_message(bot, message)
        return

    tg = message.get("from")
    chat_id = (message.get("chat") or {}).get("id")
    if tg is None or chat_id is None:
        return
    _, web_admin = await _authorized_admin(tg)
    if web_admin is None:
        await bot.send_message(chat_id, "⛔ Команда доступна только администратору KisaMore.")
        return
    await _show_pending(bot, chat_id)


async def handle_callback(bot, query: dict) -> None:
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
                sent, failed = await admin_rental_notifier.send_pending_alerts(bot)
                if welcomed or sent or failed:
                    core.logger.info(
                        "Telegram admin alert pass: welcomed=%s sent=%s failed=%s",
                        welcomed,
                        sent,
                        failed,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                core.logger.exception("Telegram admin rental alert pass failed")
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
