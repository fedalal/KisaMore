from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from html import escape

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from ..db import SessionLocal
from ..models import Allocation, Base, Plant, Planting, RackSlot
from .admin_models import TelegramAdmin
from .models import TelegramUser
from .plant_sos_chat_models import TelegramPlantSosMessage, TelegramPlantSosMessageAlert


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
        "not_owner": "SOS is available only for plants you are currently growing.",
    },
    "ru": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS по этому растению</b>\n\nОпишите, что вас насторожило. Сообщение будет отправлено администратору теплицы.\n\nОтправьте одно текстовое сообщение или /cancel.",
        "saved": "✅ SOS-сообщение отправлено администратору.",
        "cancelled": "Отправка SOS отменена.",
        "empty": "Опишите проблему текстовым сообщением.",
        "too_long": "Сообщение слишком длинное. Максимум 1500 символов.",
        "back": "🌱 Вернуться к растению",
        "not_owner": "SOS доступен только для растений, которые вы сейчас выращиваете.",
    },
    "de": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS für diese Pflanze</b>\n\nBeschreibe das Problem. Die Nachricht wird an den Gewächshaus-Administrator gesendet.\n\nSende eine Textnachricht oder /cancel.",
        "saved": "✅ Deine SOS-Nachricht wurde an den Administrator gesendet.",
        "cancelled": "SOS-Nachricht abgebrochen.",
        "empty": "Bitte beschreibe das Problem als Text.",
        "too_long": "Die Nachricht ist zu lang. Maximal 1500 Zeichen.",
        "back": "🌱 Zurück zur Pflanze",
        "not_owner": "SOS ist nur für Pflanzen verfügbar, die du aktuell anbaust.",
    },
    "fr": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS pour cette plante</b>\n\nDécrivez le problème observé. Le message sera envoyé à l’administrateur de la serre.\n\nEnvoyez un seul message texte ou /cancel.",
        "saved": "✅ Votre message SOS a été envoyé à l’administrateur.",
        "cancelled": "Message SOS annulé.",
        "empty": "Veuillez décrire le problème par écrit.",
        "too_long": "Le message est trop long. Maximum 1500 caractères.",
        "back": "🌱 Retour à la plante",
        "not_owner": "SOS est disponible uniquement pour les plantes que vous cultivez actuellement.",
    },
    "es": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS para esta planta</b>\n\nDescribe el problema que observas. El mensaje se enviará al administrador del invernadero.\n\nEnvía un mensaje de texto o /cancel.",
        "saved": "✅ Tu mensaje SOS fue enviado al administrador.",
        "cancelled": "Mensaje SOS cancelado.",
        "empty": "Describe el problema en un mensaje de texto.",
        "too_long": "El mensaje es demasiado largo. Máximo 1500 caracteres.",
        "back": "🌱 Volver a la planta",
        "not_owner": "SOS solo está disponible para las plantas que estás cultivando actualmente.",
    },
    "it": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS per questa pianta</b>\n\nDescrivi il problema che hai notato. Il messaggio sarà inviato all’amministratore della serra.\n\nInvia un messaggio di testo o /cancel.",
        "saved": "✅ Il tuo messaggio SOS è stato inviato all’amministratore.",
        "cancelled": "Messaggio SOS annullato.",
        "empty": "Descrivi il problema con un messaggio di testo.",
        "too_long": "Il messaggio è troppo lungo. Massimo 1500 caratteri.",
        "back": "🌱 Torna alla pianta",
        "not_owner": "SOS è disponibile solo per le piante che stai coltivando.",
    },
    "pt": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS para esta planta</b>\n\nDescreva o problema observado. A mensagem será enviada ao administrador da estufa.\n\nEnvie uma mensagem de texto ou /cancel.",
        "saved": "✅ Sua mensagem SOS foi enviada ao administrador.",
        "cancelled": "Mensagem SOS cancelada.",
        "empty": "Descreva o problema em uma mensagem de texto.",
        "too_long": "A mensagem é muito longa. Máximo de 1500 caracteres.",
        "back": "🌱 Voltar à planta",
        "not_owner": "SOS está disponível apenas para as plantas que você está cultivando.",
    },
    "pl": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>SOS dla tej rośliny</b>\n\nOpisz zauważony problem. Wiadomość zostanie wysłana do administratora szklarni.\n\nWyślij jedną wiadomość tekstową lub /cancel.",
        "saved": "✅ Wiadomość SOS została wysłana do administratora.",
        "cancelled": "Wiadomość SOS anulowana.",
        "empty": "Opisz problem w wiadomości tekstowej.",
        "too_long": "Wiadomość jest za długa. Maksymalnie 1500 znaków.",
        "back": "🌱 Wróć do rośliny",
        "not_owner": "SOS jest dostępny tylko dla roślin, które aktualnie uprawiasz.",
    },
    "zh": {
        "button": "🚨 SOS",
        "prompt": "🚨 <b>这株植物的 SOS</b>\n\n请描述您发现的问题。消息将发送给温室管理员。\n\n请发送一条文字消息，或发送 /cancel 取消。",
        "saved": "✅ SOS 消息已发送给管理员。",
        "cancelled": "SOS 消息已取消。",
        "empty": "请用文字描述问题。",
        "too_long": "消息过长，最多 1500 个字符。",
        "back": "🌱 返回植物",
        "not_owner": "SOS 仅适用于您当前正在种植的植物。",
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


CARD_BUTTONS = {
    "en": {"comments": "💬 Comments", "follow": "🔔 Follow", "following": "✅🔔 Following", "support": "🎁 Support", "video": "🎞 Video"},
    "ru": {"comments": "💬 Чат", "follow": "🔔 Следить", "following": "✅🔔 Слежу", "support": "🎁 Подарок", "video": "🎞 Видео", "like": "❤️ Нравится", "dislike": "👎 Плохо"},
    "de": {"comments": "💬 Kommentare", "follow": "🔔 Folgen", "following": "✅🔔 Folge ich", "support": "🎁 Unterstützen", "video": "🎞 Video"},
    "fr": {"comments": "💬 Commentaires", "follow": "🔔 Suivre", "following": "✅🔔 Suivi", "support": "🎁 Soutenir", "video": "🎞 Vidéo"},
    "es": {"comments": "💬 Comentarios", "follow": "🔔 Seguir", "following": "✅🔔 Siguiendo", "support": "🎁 Apoyar", "video": "🎞 Vídeo"},
    "it": {"comments": "💬 Commenti", "follow": "🔔 Segui", "following": "✅🔔 Seguita", "support": "🎁 Sostieni", "video": "🎞 Video"},
    "pt": {"comments": "💬 Comentários", "follow": "🔔 Seguir", "following": "✅🔔 Seguindo", "support": "🎁 Apoiar", "video": "🎞 Vídeo"},
    "pl": {"comments": "💬 Komentarze", "follow": "🔔 Obserwuj", "following": "✅🔔 Obserwuję", "support": "🎁 Wesprzyj", "video": "🎞 Wideo"},
    "zh": {"comments": "💬 评论", "follow": "🔔 关注", "following": "✅🔔 已关注", "support": "🎁 支持", "video": "🎞 视频"},
}


def _card_buttons(lang: str) -> dict:
    return CARD_BUTTONS.get(lang) or CARD_BUTTONS["en"]


SOS_CHAT_TEXT = {
    "en": {"title": "🚨 <b>SOS chat</b>", "empty": "No SOS messages yet.", "write": "✍️ Write", "you": "You", "admin": "Administrator", "resolved": "✅ Resolved", "active": "🟠 Open", "reply": "💬 <b>Administrator replied to your SOS</b>"},
    "ru": {"title": "🚨 <b>Чат SOS</b>", "empty": "Сообщений SOS пока нет.", "write": "✍️ Написать", "you": "Вы", "admin": "Администратор", "resolved": "✅ Закрыто", "active": "🟠 Открыто", "reply": "💬 <b>Ответ администратора по SOS</b>"},
    "de": {"title": "🚨 <b>SOS-Chat</b>", "empty": "Noch keine SOS-Nachrichten.", "write": "✍️ Schreiben", "you": "Du", "admin": "Administrator", "resolved": "✅ Erledigt", "active": "🟠 Offen", "reply": "💬 <b>Antwort des Administrators auf dein SOS</b>"},
    "fr": {"title": "🚨 <b>Chat SOS</b>", "empty": "Aucun message SOS pour le moment.", "write": "✍️ Écrire", "you": "Vous", "admin": "Administrateur", "resolved": "✅ Résolu", "active": "🟠 Ouvert", "reply": "💬 <b>Réponse de l’administrateur à votre SOS</b>"},
    "es": {"title": "🚨 <b>Chat SOS</b>", "empty": "Aún no hay mensajes SOS.", "write": "✍️ Escribir", "you": "Tú", "admin": "Administrador", "resolved": "✅ Resuelto", "active": "🟠 Abierto", "reply": "💬 <b>Respuesta del administrador a tu SOS</b>"},
    "it": {"title": "🚨 <b>Chat SOS</b>", "empty": "Nessun messaggio SOS.", "write": "✍️ Scrivi", "you": "Tu", "admin": "Amministratore", "resolved": "✅ Risolto", "active": "🟠 Aperto", "reply": "💬 <b>Risposta dell’amministratore al tuo SOS</b>"},
    "pt": {"title": "🚨 <b>Chat SOS</b>", "empty": "Ainda não há mensagens SOS.", "write": "✍️ Escrever", "you": "Você", "admin": "Administrador", "resolved": "✅ Resolvido", "active": "🟠 Aberto", "reply": "💬 <b>Resposta do administrador ao seu SOS</b>"},
    "pl": {"title": "🚨 <b>Czat SOS</b>", "empty": "Brak wiadomości SOS.", "write": "✍️ Napisz", "you": "Ty", "admin": "Administrator", "resolved": "✅ Zamknięte", "active": "🟠 Otwarte", "reply": "💬 <b>Odpowiedź administratora na SOS</b>"},
    "zh": {"title": "🚨 <b>SOS 聊天</b>", "empty": "暂无 SOS 消息。", "write": "✍️ 写消息", "you": "您", "admin": "管理员", "resolved": "✅ 已解决", "active": "🟠 处理中", "reply": "💬 <b>管理员回复了您的 SOS</b>"},
}


def _chat_text(lang: str) -> dict:
    return SOS_CHAT_TEXT.get(lang) or SOS_CHAT_TEXT["en"]


async def _owns_planting(user_id: int, planting_id: str) -> bool:
    async with SessionLocal() as session:
        telegram_user = await session.get(TelegramUser, user_id)
        planting = await session.get(Planting, planting_id)
        if (
            telegram_user is None
            or not telegram_user.marketplace_user_id
            or planting is None
            or not planting.cloud_allocation_id
        ):
            return False
        allocation = await session.get(Allocation, planting.cloud_allocation_id)
        return bool(
            allocation is not None
            and allocation.status == "active"
            and allocation.user_id == telegram_user.marketplace_user_id
        )


async def _active_report(session, user_id: int, planting_id: str):
    return (
        await session.execute(
            select(TelegramPlantSosReport)
            .where(
                TelegramPlantSosReport.user_id == user_id,
                TelegramPlantSosReport.planting_id == planting_id,
                TelegramPlantSosReport.status.in_(("new", "open")),
            )
            .order_by(TelegramPlantSosReport.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _append_user_message(user_id: int, planting_id: str, message: str) -> int | None:
    if not await _owns_planting(user_id, planting_id):
        return None

    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        planting = await session.get(Planting, planting_id)
        if planting is None:
            return None

        report = await _active_report(session, user_id, planting_id)
        if report is None:
            report = TelegramPlantSosReport(
                user_id=user_id,
                planting_id=planting_id,
                message=message,
                status="new",
                created_at=now,
            )
            session.add(report)
            await session.flush()

        chat_message = TelegramPlantSosMessage(
            report_id=report.id,
            sender_type="user",
            telegram_user_id=user_id,
            body=message,
            delivery_status="not_required",
            attempts=0,
            created_at=now,
        )
        session.add(chat_message)
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
                TelegramPlantSosMessageAlert(
                    message_id=chat_message.id,
                    admin_user_id=int(admin_user_id),
                    status="pending",
                    attempts=0,
                    created_at=now,
                )
            )

        await session.commit()
        return int(report.id)


async def _user_thread(user_id: int, planting_id: str):
    async with SessionLocal() as session:
        reports = list(
            (
                await session.execute(
                    select(TelegramPlantSosReport)
                    .where(
                        TelegramPlantSosReport.user_id == user_id,
                        TelegramPlantSosReport.planting_id == planting_id,
                    )
                    .order_by(TelegramPlantSosReport.created_at)
                )
            ).scalars().all()
        )
        if not reports:
            return None, []

        report_ids = [item.id for item in reports]
        messages = list(
            (
                await session.execute(
                    select(TelegramPlantSosMessage)
                    .where(TelegramPlantSosMessage.report_id.in_(report_ids))
                    .order_by(TelegramPlantSosMessage.created_at, TelegramPlantSosMessage.id)
                )
            ).scalars().all()
        )

        # Reports created by the first SOS implementation have no chat-message
        # rows. Preserve that history instead of hiding it.
        report_ids_with_messages = {item.report_id for item in messages}
        legacy = [
            (
                report.created_at,
                "user",
                report.message,
            )
            for report in reports
            if report.id not in report_ids_with_messages and report.message
        ]
        combined = [
            (item.created_at, item.sender_type, item.body)
            for item in messages
        ] + legacy
        combined.sort(key=lambda item: item[0])
        return reports[-1], combined


async def _plant_context(planting_id: str):
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(Planting, Plant, RackSlot)
                .join(Plant, Plant.id == Planting.plant_id)
                .join(RackSlot, RackSlot.id == Planting.slot_id)
                .where(Planting.id == planting_id)
                .limit(1)
            )
        ).first()


async def _show_user_thread(core, bot, chat_id: int, tg: dict, user_id: int, planting_id: str, index: int) -> None:
    lang = core.language_for(tg)
    tr = _chat_text(lang)
    context = await _plant_context(planting_id)
    if context is None:
        return
    _planting, plant, slot = context
    report, messages = await _user_thread(user_id, planting_id)
    status = tr["resolved"] if report is not None and report.status == "resolved" else tr["active"]

    header = (
        f"{tr['title']}\n"
        f"🌱 <b>{escape(core.plant_name(plant, lang))}</b> · "
        f"{slot.rack_id}/{slot.slot_number}\n"
        f"{status}"
    )
    if not messages:
        text = f"{header}\n\n{tr['empty']}"
    else:
        parts = [header, ""]
        # Telegram has a 4096 character limit. Keep the most recent messages
        # and trim individual bodies so the thread always fits comfortably.
        for _created_at, sender_type, body in messages[-10:]:
            label = tr["admin"] if sender_type == "admin" else tr["you"]
            icon = "🛡" if sender_type == "admin" else "👤"
            value = str(body or "").strip()
            if len(value) > 650:
                value = value[:647] + "..."
            parts.append(f"<b>{icon} {escape(label)}:</b>\n{escape(value)}")
        text = "\n\n".join(parts)
        if len(text) > 3800:
            text = text[-3800:]

    markup = {
        "inline_keyboard": [
            [{"text": tr["write"], "callback_data": f"sos:write:{planting_id}:{index}"}],
            [{"text": _tr(lang)["back"], "callback_data": f"plant:show:{planting_id}:{index}"}],
        ]
    }
    await bot.send_message(chat_id, text, reply_markup=markup)


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


async def _message_admin_alert_text(session, message: TelegramPlantSosMessage):
    report = await session.get(TelegramPlantSosReport, message.report_id)
    if report is None:
        return None
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
    full_name = " ".join(value for value in (author.first_name, author.last_name) if value).strip()
    if not full_name:
        full_name = author.username or f"Telegram {author.telegram_user_id}"
    username = f"@{escape(author.username)}" if author.username else "—"

    text = (
        "🚨 <b>Новое сообщение SOS</b>\n\n"
        f"Растение: <b>{escape(str(plant_name))}</b>\n"
        f"Полка {slot.rack_id} · контейнер {slot.slot_number}\n"
        f"Пользователь: <b>{escape(full_name)}</b>\n"
        f"Username: {username}\n\n"
        f"<b>Сообщение:</b>\n{escape(message.body)}\n\n"
        "Ответить можно в разделе <b>/admin → SOS</b>."
    )
    return text


async def _send_pending_alerts(bot) -> None:
    async with SessionLocal() as session:
        # Legacy first-generation alerts are kept so already queued SOS reports
        # are not lost during deployment.
        legacy_alerts = list(
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
        for alert in legacy_alerts:
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
                await bot.send_message(int(admin_user.telegram_user_id), text, reply_markup=markup)
                alert.status = "sent"
                alert.sent_at = datetime.now(timezone.utc)
                alert.last_error = None
            except Exception as exc:
                alert.attempts += 1
                alert.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                if alert.attempts >= MAX_ATTEMPTS:
                    alert.status = "failed"

        message_alerts = list(
            (
                await session.execute(
                    select(TelegramPlantSosMessageAlert)
                    .where(
                        TelegramPlantSosMessageAlert.status == "pending",
                        TelegramPlantSosMessageAlert.attempts < MAX_ATTEMPTS,
                    )
                    .order_by(TelegramPlantSosMessageAlert.id)
                    .limit(50)
                )
            ).scalars().all()
        )
        for alert in message_alerts:
            admin_user = await session.get(TelegramUser, alert.admin_user_id)
            admin = await session.get(TelegramAdmin, alert.admin_user_id)
            message = await session.get(TelegramPlantSosMessage, alert.message_id)
            if (
                admin_user is None
                or admin is None
                or not admin.enabled
                or not admin_user.is_active
                or message is None
            ):
                alert.status = "skipped"
                continue
            text = await _message_admin_alert_text(session, message)
            if text is None:
                alert.status = "skipped"
                continue
            try:
                await bot.send_message(int(admin_user.telegram_user_id), text)
                alert.status = "sent"
                alert.sent_at = datetime.now(timezone.utc)
                alert.last_error = None
            except Exception as exc:
                alert.attempts += 1
                alert.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                if alert.attempts >= MAX_ATTEMPTS:
                    alert.status = "failed"

        replies = list(
            (
                await session.execute(
                    select(TelegramPlantSosMessage)
                    .where(
                        TelegramPlantSosMessage.sender_type == "admin",
                        TelegramPlantSosMessage.delivery_status == "pending",
                        TelegramPlantSosMessage.attempts < MAX_ATTEMPTS,
                    )
                    .order_by(TelegramPlantSosMessage.id)
                    .limit(50)
                )
            ).scalars().all()
        )
        for message in replies:
            report = await session.get(TelegramPlantSosReport, message.report_id)
            user = await session.get(TelegramUser, report.user_id) if report else None
            if report is None or user is None or not user.is_active:
                message.delivery_status = "skipped"
                continue
            context = await _plant_context(report.planting_id)
            if context is None:
                message.delivery_status = "skipped"
                continue
            _planting, plant, slot = context
            lang = (user.language_code or "en").lower().replace("_", "-").split("-", 1)[0]
            tr = _chat_text(lang)
            names = plant.names or {}
            plant_name = names.get(lang) or names.get("en") or names.get("ru") or plant.code
            text = (
                f"{tr['reply']}\n\n"
                f"🌱 <b>{escape(str(plant_name))}</b> · {slot.rack_id}/{slot.slot_number}\n\n"
                f"{escape(message.body)}"
            )
            markup = {
                "inline_keyboard": [[
                    {
                        "text": tr["title"].replace("<b>", "").replace("</b>", ""),
                        "callback_data": f"sos:start:{report.planting_id}:0",
                    }
                ]]
            }
            try:
                await bot.send_message(int(user.telegram_user_id), text, reply_markup=markup)
                message.delivery_status = "sent"
                message.delivered_at = datetime.now(timezone.utc)
                message.last_error = None
            except Exception as exc:
                message.attempts += 1
                message.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                if message.attempts >= MAX_ATTEMPTS:
                    message.delivery_status = "failed"

        if legacy_alerts or message_alerts or replies:
            await session.commit()


def install(core) -> None:
    if getattr(core, "_plant_sos_installed", False):
        return

    previous_handle_callback = core.handle_callback
    previous_handle_message = core.handle_message
    previous_follow_notification_loop = core.follow_notification_loop

    def plant_keyboard(lang: str, card, index: int, total: int) -> dict:
        # Counts already appear in the plant caption, so button labels stay
        # descriptive but do not repeat the same numbers.
        labels = _card_buttons(lang)
        like_text = labels.get("like") or core.st(lang, "like")
        dislike_text = labels.get("dislike") or core.st(lang, "dislike")
        if card.my_vote == "like":
            like_text = f"✅ {like_text}"
        if card.my_vote == "dislike":
            dislike_text = f"✅ {dislike_text}"

        rows = [
            [
                {
                    "text": like_text,
                    "callback_data": f"vote:like:{card.planting.id}:{index}",
                },
                {
                    "text": dislike_text,
                    "callback_data": f"vote:dislike:{card.planting.id}:{index}",
                },
                {
                    "text": labels["comments"],
                    "callback_data": f"comment:list:{card.planting.id}:{index}",
                },
            ],
            [
                {
                    "text": labels["following"] if card.following else labels["follow"],
                    "callback_data": f"follow:{card.planting.id}:{index}",
                },
                {
                    "text": labels["support"],
                    "callback_data": f"gift:menu:{card.planting.id}:{index}",
                },
                {
                    "text": labels["video"],
                    "callback_data": f"timelapse:{card.planting.id}",
                },
            ],
        ]

        nav = []
        if bool(getattr(card, "is_owner", False)):
            nav.append(
                {
                    "text": _tr(lang)["button"],
                    "callback_data": f"sos:start:{card.planting.id}:{index}",
                }
            )
        if index > 0:
            nav.append({"text": "⬅️", "callback_data": f"feed:{index - 1}"})
        nav.append({"text": "🏠", "callback_data": "menu:home"})
        if index + 1 < total:
            nav.append({"text": "➡️", "callback_data": f"feed:{index + 1}"})
        rows.append(nav)

        return {"inline_keyboard": rows}

    async def handle_callback(bot, query: dict) -> None:
        data = str(query.get("data") or "")
        if not data.startswith("sos:"):
            await previous_handle_callback(bot, query)
            return

        qid = query.get("id")
        tg = query.get("from")
        chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
        if not qid or tg is None or chat_id is None:
            return

        parts = data.split(":", 3)
        if len(parts) != 4 or parts[1] not in ("start", "write"):
            await bot.answer_callback_query(qid)
            return
        planting_id = parts[2]
        try:
            index = int(parts[3])
        except ValueError:
            index = 0

        user, _ = await core.get_or_create_user(tg)
        lang = core.language_for(tg)
        if not await _owns_planting(user.id, planting_id):
            await bot.answer_callback_query(
                qid,
                text=_tr(lang)["not_owner"],
                show_alert=True,
            )
            return

        await bot.answer_callback_query(qid)
        if parts[1] == "start":
            await _show_user_thread(core, bot, chat_id, tg, user.id, planting_id, index)
            return

        await core.set_state(
            user.id,
            "plant_sos",
            target_type="planting",
            target_id=planting_id,
            payload={"index": index},
        )
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
        report_id = await _append_user_message(user.id, planting_id, text)
        if report_id is None:
            await core.clear_state(user.id)
            await previous_handle_message(bot, message)
            return

        await core.clear_state(user.id)
        await bot.send_message(
            chat_id,
            tr["saved"],
            reply_markup={
                "inline_keyboard": [
                    [{
                        "text": _chat_text(lang)["title"].replace("<b>", "").replace("</b>", ""),
                        "callback_data": f"sos:start:{planting_id}:{index}",
                    }],
                    [{
                        "text": tr["back"],
                        "callback_data": f"plant:show:{planting_id}:{index}",
                    }],
                ]
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
