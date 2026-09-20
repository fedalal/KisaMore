from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from html import escape

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from ..db import SessionLocal
from ..models import Base, Plant, Planting, RackSlot
from .admin_models import TelegramAdmin
from .models import TelegramUser


MAX_ATTEMPTS = 5

SOS_TEXT = {
    "en": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS for this plant</b>\n\nDescribe what looks wrong. Your message will be sent to the greenhouse administrator.\n\nSend one text message or /cancel.",
        "saved": "✅ Your SOS message has been sent to the administrator.",
        "cancelled": "SOS message cancelled.",
        "empty": "Please describe the problem in a text message.",
        "too_long": "The message is too long. Please keep it under 1500 characters.",
        "back": "🌱 Back to plant",
    },
    "ru": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS по этому растению</b>\n\nОпишите, что вас насторожило. Сообщение будет отправлено администратору теплицы.\n\nОтправьте одно текстовое сообщение или /cancel.",
        "saved": "✅ SOS-сообщение отправлено администратору.",
        "cancelled": "Отправка SOS отменена.",
        "empty": "Опишите проблему текстовым сообщением.",
        "too_long": "Сообщение слишком длинное. Максимум 1500 символов.",
        "back": "🌱 Вернуться к растению",
    },
    "de": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS für diese Pflanze</b>\n\nBeschreibe das Problem. Die Nachricht wird an den Gewächshaus-Administrator gesendet.\n\nSende eine Textnachricht oder /cancel.",
        "saved": "✅ Deine SOS-Nachricht wurde an den Administrator gesendet.",
        "cancelled": "SOS-Nachricht abgebrochen.",
        "empty": "Bitte beschreibe das Problem als Text.",
        "too_long": "Die Nachricht ist zu lang. Maximal 1500 Zeichen.",
        "back": "🌱 Zurück zur Pflanze",
    },
    "fr": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS pour cette plante</b>\n\nDécrivez le problème observé. Le message sera envoyé à l’administrateur de la serre.\n\nEnvoyez un seul message texte ou /cancel.",
        "saved": "✅ Votre message SOS a été envoyé à l’administrateur.",
        "cancelled": "Message SOS annulé.",
        "empty": "Veuillez décrire le problème par écrit.",
        "too_long": "Le message est trop long. Maximum 1500 caractères.",
        "back": "🌱 Retour à la plante",
    },
    "es": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS para esta planta</b>\n\nDescribe el problema que observas. El mensaje se enviará al administrador del invernadero.\n\nEnvía un mensaje de texto o /cancel.",
        "saved": "✅ Tu mensaje SOS fue enviado al administrador.",
        "cancelled": "Mensaje SOS cancelado.",
        "empty": "Describe el problema en un mensaje de texto.",
        "too_long": "El mensaje es demasiado largo. Máximo 1500 caracteres.",
        "back": "🌱 Volver a la planta",
    },
    "it": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS per questa pianta</b>\n\nDescrivi il problema che hai notato. Il messaggio sarà inviato all’amministratore della serra.\n\nInvia un messaggio di testo o /cancel.",
        "saved": "✅ Il tuo messaggio SOS è stato inviato all’amministratore.",
        "cancelled": "Messaggio SOS annullato.",
        "empty": "Descrivi il problema con un messaggio di testo.",
        "too_long": "Il messaggio è troppo lungo. Massimo 1500 caratteri.",
        "back": "🌱 Torna alla pianta",
    },
    "pt": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS para esta planta</b>\n\nDescreva o problema observado. A mensagem será enviada ao administrador da estufa.\n\nEnvie uma mensagem de texto ou /cancel.",
        "saved": "✅ Sua mensagem SOS foi enviada ao administrador.",
        "cancelled": "Mensagem SOS cancelada.",
        "empty": "Descreva o problema em uma mensagem de texto.",
        "too_long": "A mensagem é muito longa. Máximo de 1500 caracteres.",
        "back": "🌱 Voltar à planta",
    },
    "pl": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS dla tej rośliny</b>\n\nOpisz zauważony problem. Wiadomość zostanie wysłana do administratora szklarni.\n\nWyślij jedną wiadomość tekstową lub /cancel.",
        "saved": "✅ Wiadomość SOS została wysłana do administratora.",
        "cancelled": "Wiadomość SOS anulowana.",
        "empty": "Opisz problem w wiadomości tekstowej.",
        "too_long": "Wiadomość jest za długa. Maksymalnie 1500 znaków.",
        "back": "🌱 Wróć do rośliny",
    },
    "zh": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>这株植物的 SOS</b>\n\n请描述您发现的问题。消息将发送给温室管理员。\n\n请发送一条文字消息，或发送 /cancel 取消。",
        "saved": "✅ SOS 消息已发送给管理员。",
        "cancelled": "SOS 消息已取消。",
        "empty": "请用文字描述问题。",
        "too_long": "消息过长，最多 1500 个字符。",
        "back": "🌱 返回植物",
    },
}


class TelegramPlantSosReport(Base):
    __tablename__ = "telegram_plant_sos_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), index=True, nullable=False
    )
    planting_id: Mapped[str] = mapped_column(
        ForeignKey("plantings.id"), index=True, nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TelegramPlantSosAlert(Base):
    __tablename__ = "telegram_plant_sos_alerts"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "admin_user_id",
            name="uq_telegram_plant_sos_alert",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_plant_sos_reports.id"), index=True, nullable=False
    )
    admin_user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def _tr(lang: str) -> dict:
    return SOS_TEXT.get(lang) or SOS_TEXT["en"]


async def _create_report(user_id: int, planting_id: str, message: str) -> int | None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        planting = await session.get(Planting, planting_id)
        if planting is None:
            return None

        report = TelegramPlantSosReport(
            user_id=user_id,
            planting_id=planting_id,
            message=message,
            status="new",
            created_at=now,
        )
        session.add(report)
        await session.flush()

        admin_ids = list(
            (
                await session.execute(
                    select(TelegramAdmin.user_id)
                    .join(TelegramUser, TelegramUser.id == TelegramAdmin.user_id)
                    .where(
                        TelegramAdmin.enabled.is_(True),
                        TelegramUser.is_active.is_(True),
                    )
                )
            ).scalars().all()
        )
        for admin_user_id in admin_ids:
            session.add(
                TelegramPlantSosAlert(
                    report_id=report.id,
                    admin_user_id=int(admin_user_id),
                    status="pending",
                    attempts=0,
                    created_at=now,
                )
            )
        await session.commit()
        return int(report.id)


async def _admin_alert_text(session, report: TelegramPlantSosReport) -> tuple[str, dict] | None:
    author = await session.get(TelegramUser, report.user_id)
    row = (
        await session.execute(
            select(Planting, Plant, RackSlot)
            .join(Plant, Plant.id == Planting.plant_id)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .where(Planting.id == report.planting_id)
            .limit(1)
        )
    ).first()
    if author is None or row is None:
        return None

    _planting, plant, slot = row
    names = plant.names or {}
    plant_name = names.get("ru") or names.get("en") or next(
        (str(value) for value in names.values() if value),
        plant.code,
    )
    full_name = " ".join(
        value for value in (author.first_name, author.last_name) if value
    ).strip()
    if not full_name:
        full_name = author.username or f"Telegram {author.telegram_user_id}"
    username = f"@{escape(author.username)}" if author.username else "—"

    text = (
        "🚨 <b>SOS по растению</b>\n\n"
        f"Растение: <b>{escape(str(plant_name))}</b>\n"
        f"Полка {slot.rack_id} · контейнер {slot.slot_number}\n"
        f"Пользователь: <b>{escape(full_name)}</b>\n"
        f"Username: {username}\n"
        f"Telegram ID: <code>{int(author.telegram_user_id)}</code>\n\n"
        f"<b>Сообщение:</b>\n{escape(report.message)}"
    )
    markup = {
        "inline_keyboard": [[
            {
                "text": "🌱 Открыть растение",
                "callback_data": f"plant:show:{report.planting_id}:0",
            }
        ]]
    }
    return text, markup


async def _send_pending_alerts(bot) -> None:
    async with SessionLocal() as session:
        alerts = list(
            (
                await session.execute(
                    select(TelegramPlantSosAlert)
                    .where(
                        TelegramPlantSosAlert.status == "pending",
                        TelegramPlantSosAlert.attempts < MAX_ATTEMPTS,
                    )
                    .order_by(TelegramPlantSosAlert.id)
                    .limit(50)
                )
            ).scalars().all()
        )

        for alert in alerts:
            admin_user = await session.get(TelegramUser, alert.admin_user_id)
            admin = await session.get(TelegramAdmin, alert.admin_user_id)
            report = await session.get(TelegramPlantSosReport, alert.report_id)
            if (
                admin_user is None
                or admin is None
                or not admin.enabled
                or not admin_user.is_active
                or report is None
            ):
                alert.status = "skipped"
                continue

            prepared = await _admin_alert_text(session, report)
            if prepared is None:
                alert.status = "skipped"
                continue
            text, markup = prepared
            try:
                await bot.send_message(
                    int(admin_user.telegram_user_id),
                    text,
                    reply_markup=markup,
                )
                alert.status = "sent"
                alert.sent_at = datetime.now(timezone.utc)
                alert.last_error = None
            except Exception as exc:
                alert.attempts += 1
                alert.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                if alert.attempts >= MAX_ATTEMPTS:
                    alert.status = "failed"

        if alerts:
            await session.commit()


def install(core) -> None:
    if getattr(core, "_plant_sos_installed", False):
        return

    previous_plant_keyboard = core.plant_keyboard
    previous_handle_callback = core.handle_callback
    previous_handle_message = core.handle_message
    previous_follow_notification_loop = core.follow_notification_loop

    def plant_keyboard(lang: str, card, index: int, total: int) -> dict:
        markup = previous_plant_keyboard(lang, card, index, total)
        rows = [list(row) for row in markup.get("inline_keyboard", [])]
        sos_row = [{
            "text": _tr(lang)["button"],
            "callback_data": f"sos:start:{card.planting.id}:{index}",
        }]
        if rows:
            rows.insert(max(0, len(rows) - 1), sos_row)
        else:
            rows.append(sos_row)
        return {"inline_keyboard": rows}

    async def handle_callback(bot, query: dict) -> None:
        data = str(query.get("data") or "")
        if not data.startswith("sos:start:"):
            await previous_handle_callback(bot, query)
            return

        qid = query.get("id")
        tg = query.get("from")
        chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
        if not qid or tg is None or chat_id is None:
            return

        parts = data.split(":", 3)
        if len(parts) != 4:
            await bot.answer_callback_query(qid)
            return
        planting_id = parts[2]
        try:
            index = int(parts[3])
        except ValueError:
            index = 0

        user, _ = await core.get_or_create_user(tg)
        lang = core.language_for(tg)
        await core.set_state(
            user.id,
            "plant_sos",
            target_type="planting",
            target_id=planting_id,
            payload={"index": index},
        )
        await bot.answer_callback_query(qid)
        await bot.send_message(chat_id, _tr(lang)["prompt"])

    async def handle_message(bot, message: dict) -> None:
        tg = message.get("from")
        chat_id = (message.get("chat") or {}).get("id")
        if tg is None or chat_id is None:
            await previous_handle_message(bot, message)
            return

        user, _ = await core.get_or_create_user(tg)
        state = await core.get_state(user.id)
        if state is None or state.mode != "plant_sos":
            await previous_handle_message(bot, message)
            return

        lang = core.language_for(tg)
        tr = _tr(lang)
        text = str(message.get("text") or "").strip()
        command = text.lower().split("@", 1)[0]

        if command == "/cancel":
            await core.clear_state(user.id)
            await bot.send_message(chat_id, tr["cancelled"])
            return
        if text.startswith("/"):
            await previous_handle_message(bot, message)
            return
        if not text:
            await bot.send_message(chat_id, tr["empty"])
            return
        if len(text) > 1500:
            await bot.send_message(chat_id, tr["too_long"])
            return
        if state.target_type != "planting" or not state.target_id:
            await core.clear_state(user.id)
            await previous_handle_message(bot, message)
            return

        planting_id = state.target_id
        index = int((state.payload or {}).get("index") or 0)
        report_id = await _create_report(user.id, planting_id, text)
        if report_id is None:
            await core.clear_state(user.id)
            await previous_handle_message(bot, message)
            return

        await core.clear_state(user.id)
        await bot.send_message(
            chat_id,
            tr["saved"],
            reply_markup={
                "inline_keyboard": [[
                    {
                        "text": tr["back"],
                        "callback_data": f"plant:show:{planting_id}:{index}",
                    }
                ]]
            },
        )

    async def follow_notification_loop(bot) -> None:
        async def sos_loop() -> None:
            while True:
                try:
                    await _send_pending_alerts(bot)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    core.logger.exception("Telegram plant SOS alert pass failed")
                await asyncio.sleep(5)

        await asyncio.gather(
            previous_follow_notification_loop(bot),
            sos_loop(),
        )

    core.plant_keyboard = plant_keyboard
    core.handle_callback = handle_callback
    core.handle_message = handle_message
    core.follow_notification_loop = follow_notification_loop
    core._plant_sos_installed = True
