from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy import select

from ..models import Plant, RackSlot
from ..watering_service import aware_utc
from .activity_notifier import TelegramActivityDelivery, user_language
from .models import TelegramRentalRequest, TelegramUser


TEXTS = {
    "en": {
        "approved": "✅ <b>Rental request approved!</b>\n\n{plant}\nRack {rack} · Container {slot}\n\nThe container is now reserved for you.\nWe will let you know when your plant is planted.",
        "rejected": "❌ <b>Rental request declined</b>\n\n{plant}\nRack {rack} · Container {slot}{reason}{refund}",
        "reason": "\n\nReason: {reason}",
        "refund": "\n\nⓀ {amount} have been returned to your balance.",
        "garden": "🪴 Open My Garden",
    },
    "ru": {
        "approved": "✅ <b>Заявка на аренду одобрена!</b>\n\n{plant}\nПолка {rack} · контейнер {slot}\n\nКонтейнер закреплён за вами.\nМы сообщим, когда растение будет посажено.",
        "rejected": "❌ <b>Заявка на аренду отклонена</b>\n\n{plant}\nПолка {rack} · контейнер {slot}{reason}{refund}",
        "reason": "\n\nПричина: {reason}",
        "refund": "\n\nⓀ {amount} возвращены на ваш баланс.",
        "garden": "🪴 Открыть мой сад",
    },
    "de": {
        "approved": "✅ <b>Mietanfrage genehmigt!</b>\n\n{plant}\nRegal {rack} · Behälter {slot}\n\nDer Behälter ist jetzt für dich reserviert.\nWir informieren dich, sobald die Pflanze eingesetzt wurde.",
        "rejected": "❌ <b>Mietanfrage abgelehnt</b>\n\n{plant}\nRegal {rack} · Behälter {slot}{reason}{refund}",
        "reason": "\n\nGrund: {reason}",
        "refund": "\n\nⓀ {amount} wurden deinem Guthaben zurückerstattet.",
        "garden": "🪴 Meinen Garten öffnen",
    },
    "fr": {
        "approved": "✅ <b>Demande de location approuvée !</b>\n\n{plant}\nÉtagère {rack} · bac {slot}\n\nLe bac vous est maintenant réservé.\nNous vous informerons quand la plante sera mise en culture.",
        "rejected": "❌ <b>Demande de location refusée</b>\n\n{plant}\nÉtagère {rack} · bac {slot}{reason}{refund}",
        "reason": "\n\nMotif : {reason}",
        "refund": "\n\nⓀ {amount} ont été recrédités sur votre solde.",
        "garden": "🪴 Ouvrir mon jardin",
    },
    "es": {
        "approved": "✅ <b>¡Solicitud de alquiler aprobada!</b>\n\n{plant}\nEstante {rack} · contenedor {slot}\n\nEl contenedor ya está reservado para ti.\nTe avisaremos cuando se plante.",
        "rejected": "❌ <b>Solicitud de alquiler rechazada</b>\n\n{plant}\nEstante {rack} · contenedor {slot}{reason}{refund}",
        "reason": "\n\nMotivo: {reason}",
        "refund": "\n\nⓀ {amount} se han devuelto a tu saldo.",
        "garden": "🪴 Abrir Mi Jardín",
    },
    "it": {
        "approved": "✅ <b>Richiesta di noleggio approvata!</b>\n\n{plant}\nScaffale {rack} · contenitore {slot}\n\nIl contenitore è ora riservato a te.\nTi avviseremo quando la pianta sarà messa a dimora.",
        "rejected": "❌ <b>Richiesta di noleggio rifiutata</b>\n\n{plant}\nScaffale {rack} · contenitore {slot}{reason}{refund}",
        "reason": "\n\nMotivo: {reason}",
        "refund": "\n\nⓀ {amount} sono stati restituiti al tuo saldo.",
        "garden": "🪴 Apri il mio giardino",
    },
    "pt": {
        "approved": "✅ <b>Pedido de aluguel aprovado!</b>\n\n{plant}\nPrateleira {rack} · recipiente {slot}\n\nO recipiente agora está reservado para você.\nAvisaremos quando a planta for colocada para crescer.",
        "rejected": "❌ <b>Pedido de aluguel recusado</b>\n\n{plant}\nPrateleira {rack} · recipiente {slot}{reason}{refund}",
        "reason": "\n\nMotivo: {reason}",
        "refund": "\n\nⓀ {amount} foram devolvidos ao seu saldo.",
        "garden": "🪴 Abrir meu jardim",
    },
    "pl": {
        "approved": "✅ <b>Wniosek o wynajem zatwierdzony!</b>\n\n{plant}\nPółka {rack} · pojemnik {slot}\n\nPojemnik jest teraz zarezerwowany dla Ciebie.\nPowiadomimy Cię, gdy roślina zostanie posadzona.",
        "rejected": "❌ <b>Wniosek o wynajem odrzucony</b>\n\n{plant}\nPółka {rack} · pojemnik {slot}{reason}{refund}",
        "reason": "\n\nPowód: {reason}",
        "refund": "\n\nⓀ {amount} zostało zwrócone na Twoje saldo.",
        "garden": "🪴 Otwórz mój ogród",
    },
    "zh": {
        "approved": "✅ <b>租用申请已批准！</b>\n\n{plant}\n架子 {rack} · 容器 {slot}\n\n该容器现已为您保留。\n植物种下后我们会通知您。",
        "rejected": "❌ <b>租用申请已拒绝</b>\n\n{plant}\n架子 {rack} · 容器 {slot}{reason}{refund}",
        "reason": "\n\n原因：{reason}",
        "refund": "\n\nⓀ {amount} 已退回您的余额。",
        "garden": "🪴 打开我的花园",
    },
}


def _plant_name(plant: Plant, lang: str) -> str:
    names = plant.names or {}
    value = names.get(lang) or names.get("en") or names.get("ru")
    if not value:
        value = next((item for item in names.values() if item), plant.code)
    return escape(str(value))


def _reason_text(raw: str | None, lang: str) -> str:
    reason = (raw or "").strip()
    if not reason or reason.startswith("allocation:"):
        return ""
    known = {
        "Rejected by administrator": {
            "ru": "отклонено администратором",
            "en": "rejected by administrator",
        },
        "Container allocated to another request": {
            "ru": "контейнер был выделен другой заявке",
            "en": "the container was allocated to another request",
        },
    }
    translated = known.get(reason, {}).get(lang) or reason
    return TEXTS[lang]["reason"].format(reason=escape(translated))


async def discover_rental_decisions(session, now: datetime, recent_hours: int = 24) -> int:
    """Queue one Telegram message for each recent approved/rejected rental request."""
    cutoff = now - timedelta(hours=max(1, recent_hours))
    rows = (
        await session.execute(
            select(TelegramRentalRequest, TelegramUser, RackSlot, Plant)
            .join(TelegramUser, TelegramUser.id == TelegramRentalRequest.user_id)
            .join(RackSlot, RackSlot.id == TelegramRentalRequest.slot_id)
            .join(Plant, Plant.id == TelegramRentalRequest.plant_id)
            .where(
                TelegramRentalRequest.status.in_(("approved", "rejected")),
                TelegramRentalRequest.updated_at >= cutoff,
                TelegramUser.is_active.is_(True),
            )
            .order_by(TelegramRentalRequest.updated_at)
        )
    ).all()

    created = 0
    for request, telegram_user, slot, plant in rows:
        status = request.status
        event_key = f"rental_{status}:{request.id}"
        if await session.get(TelegramActivityDelivery, event_key) is not None:
            continue

        lang = user_language(telegram_user.language_code)
        texts = TEXTS.get(lang) or TEXTS["en"]
        if status == "approved":
            text = texts["approved"].format(
                plant=_plant_name(plant, lang),
                rack=slot.rack_id,
                slot=slot.slot_number,
            )
        else:
            refund = ""
            price = max(0, int(request.price_kisa or 0))
            if price and request.refunded_at is not None:
                refund = texts["refund"].format(amount=price)
            text = texts["rejected"].format(
                plant=_plant_name(plant, lang),
                rack=slot.rack_id,
                slot=slot.slot_number,
                reason=_reason_text(request.note, lang),
                refund=refund,
            )

        event_time = aware_utc(request.updated_at) or now
        session.add(
            TelegramActivityDelivery(
                event_key=event_key,
                telegram_user_id=telegram_user.telegram_user_id,
                kind=f"rental_{status}",
                payload={
                    "text": text,
                    "button": texts["garden"],
                    "callback_data": "menu:garden",
                    "rental_request_id": request.id,
                },
                status="pending",
                attempts=0,
                created_at=event_time,
            )
        )
        created += 1

    if created:
        await session.commit()
    return created
