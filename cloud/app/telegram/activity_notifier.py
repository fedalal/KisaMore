from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from html import escape
import logging
import os

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from ..db import SessionLocal, create_tables, engine
from ..models import Allocation, Base, Plant, Planting, RackSlot, WateringTask
from ..watering_service import aware_utc, farm_zone
from .bot import TelegramBotAPI
from .models import TelegramUser


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

CHECK_SECONDS = max(5, int(os.getenv("KISAMORE_TELEGRAM_ACTIVITY_CHECK_SECONDS", "10")))
RECENT_HOURS = max(1, int(os.getenv("KISAMORE_TELEGRAM_ACTIVITY_RECENT_HOURS", "24")))
MAX_ATTEMPTS = max(1, int(os.getenv("KISAMORE_TELEGRAM_ACTIVITY_MAX_ATTEMPTS", "5")))
ACTIVE_PLANTING_STATUSES = ("planned", "growing", "ready")


class TelegramActivityDelivery(Base):
    """Persistent outbox marker so lifecycle messages are not sent repeatedly."""

    __tablename__ = "telegram_activity_deliveries"

    event_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


TEXTS = {
    "en": {
        "started": "🌱 <b>Your plant has been planted!</b>\n\n{plant}\nRack {rack} · Container {slot}\nStarted: {time}\n\nWe will also let you know when it is watered.",
        "ready": "🌿 <b>Your plant is ready!</b>\n\n{plant}\nRack {rack} · Container {slot}\nReady: {time}\n\nThe growing stage is complete and scheduled watering has stopped. Your plant is ready for harvest.",
        "harvested": "✅ <b>Growing cycle completed</b>\n\n{plant}\nRack {rack} · Container {slot}\nHarvested: {time}\n\nThank you for growing with KisaMore!",
        "watered": "💧 <b>Your plant has been watered</b>\n\n{plant}\nRack {rack} · Container {slot}\nWater: <b>{ml} ml</b>\n{kind}Completed: {time}",
        "extra": "Additional watering\n",
        "open": "🌱 Open my plant",
        "garden": "🪴 Open My Garden",
    },
    "ru": {
        "started": "🌱 <b>Ваше растение посажено!</b>\n\n{plant}\nПолка {rack} · контейнер {slot}\nПосажено: {time}\n\nТеперь я буду сообщать вам и о каждом выполненном поливе.",
        "ready": "🌿 <b>Ваше растение готово!</b>\n\n{plant}\nПолка {rack} · контейнер {slot}\nГотово: {time}\n\nЭтап выращивания завершён, плановые поливы остановлены. Растение готово к сбору.",
        "harvested": "✅ <b>Выращивание завершено</b>\n\n{plant}\nПолка {rack} · контейнер {slot}\nУбрано: {time}\n\nВаш цикл выращивания завершён. Спасибо, что выращивали вместе с KisaMore!",
        "watered": "💧 <b>Ваше растение полито</b>\n\n{plant}\nПолка {rack} · контейнер {slot}\nОбъём воды: <b>{ml} мл</b>\n{kind}Выполнено: {time}",
        "extra": "Дополнительный полив\n",
        "open": "🌱 Открыть моё растение",
        "garden": "🪴 Открыть мой сад",
    },
    "de": {
        "started": "🌱 <b>Deine Pflanze wurde gepflanzt!</b>\n\n{plant}\nRegal {rack} · Behälter {slot}\nGestartet: {time}\n\nWir informieren dich auch über jede Bewässerung.",
        "ready": "🌿 <b>Deine Pflanze ist bereit!</b>\n\n{plant}\nRegal {rack} · Behälter {slot}\nBereit: {time}\n\nDie Wachstumsphase ist abgeschlossen und die planmäßige Bewässerung wurde beendet. Die Pflanze ist erntereif.",
        "harvested": "✅ <b>Anbauzyklus abgeschlossen</b>\n\n{plant}\nRegal {rack} · Behälter {slot}\nGeerntet: {time}\n\nDanke, dass du mit KisaMore angebaut hast!",
        "watered": "💧 <b>Deine Pflanze wurde bewässert</b>\n\n{plant}\nRegal {rack} · Behälter {slot}\nWasser: <b>{ml} ml</b>\n{kind}Erledigt: {time}",
        "extra": "Zusätzliche Bewässerung\n",
        "open": "🌱 Meine Pflanze öffnen",
        "garden": "🪴 Meinen Garten öffnen",
    },
    "fr": {
        "started": "🌱 <b>Votre plante a été mise en culture !</b>\n\n{plant}\nÉtagère {rack} · bac {slot}\nDébut : {time}\n\nNous vous informerons aussi de chaque arrosage.",
        "ready": "🌿 <b>Votre plante est prête !</b>\n\n{plant}\nÉtagère {rack} · bac {slot}\nPrête : {time}\n\nLa phase de croissance est terminée et les arrosages programmés sont arrêtés. La plante est prête à être récoltée.",
        "harvested": "✅ <b>Cycle de culture terminé</b>\n\n{plant}\nÉtagère {rack} · bac {slot}\nRécoltée : {time}\n\nMerci d’avoir cultivé avec KisaMore !",
        "watered": "💧 <b>Votre plante a été arrosée</b>\n\n{plant}\nÉtagère {rack} · bac {slot}\nEau : <b>{ml} ml</b>\n{kind}Terminé : {time}",
        "extra": "Arrosage supplémentaire\n",
        "open": "🌱 Ouvrir ma plante",
        "garden": "🪴 Ouvrir mon jardin",
    },
    "es": {
        "started": "🌱 <b>¡Tu planta ha sido plantada!</b>\n\n{plant}\nEstante {rack} · contenedor {slot}\nInicio: {time}\n\nTambién te avisaremos de cada riego.",
        "ready": "🌿 <b>¡Tu planta está lista!</b>\n\n{plant}\nEstante {rack} · contenedor {slot}\nLista: {time}\n\nLa etapa de crecimiento ha terminado y el riego programado se ha detenido. La planta está lista para cosechar.",
        "harvested": "✅ <b>Ciclo de cultivo completado</b>\n\n{plant}\nEstante {rack} · contenedor {slot}\nCosechada: {time}\n\n¡Gracias por cultivar con KisaMore!",
        "watered": "💧 <b>Tu planta ha sido regada</b>\n\n{plant}\nEstante {rack} · contenedor {slot}\nAgua: <b>{ml} ml</b>\n{kind}Completado: {time}",
        "extra": "Riego adicional\n",
        "open": "🌱 Abrir mi planta",
        "garden": "🪴 Abrir Mi Jardín",
    },
    "it": {
        "started": "🌱 <b>La tua pianta è stata piantata!</b>\n\n{plant}\nScaffale {rack} · contenitore {slot}\nInizio: {time}\n\nTi avviseremo anche per ogni irrigazione.",
        "ready": "🌿 <b>La tua pianta è pronta!</b>\n\n{plant}\nScaffale {rack} · contenitore {slot}\nPronta: {time}\n\nLa fase di crescita è terminata e l'irrigazione programmata è stata interrotta. La pianta è pronta per la raccolta.",
        "harvested": "✅ <b>Ciclo di coltivazione completato</b>\n\n{plant}\nScaffale {rack} · contenitore {slot}\nRaccolta: {time}\n\nGrazie per aver coltivato con KisaMore!",
        "watered": "💧 <b>La tua pianta è stata irrigata</b>\n\n{plant}\nScaffale {rack} · contenitore {slot}\nAcqua: <b>{ml} ml</b>\n{kind}Completato: {time}",
        "extra": "Irrigazione aggiuntiva\n",
        "open": "🌱 Apri la mia pianta",
        "garden": "🪴 Apri il mio giardino",
    },
    "pt": {
        "started": "🌱 <b>Sua planta foi plantada!</b>\n\n{plant}\nPrateleira {rack} · recipiente {slot}\nInício: {time}\n\nTambém avisaremos sobre cada rega.",
        "ready": "🌿 <b>Sua planta está pronta!</b>\n\n{plant}\nPrateleira {rack} · recipiente {slot}\nPronta: {time}\n\nA fase de crescimento terminou e a rega programada foi interrompida. A planta está pronta para a colheita.",
        "harvested": "✅ <b>Ciclo de cultivo concluído</b>\n\n{plant}\nPrateleira {rack} · recipiente {slot}\nColhida: {time}\n\nObrigado por cultivar com KisaMore!",
        "watered": "💧 <b>Sua planta foi regada</b>\n\n{plant}\nPrateleira {rack} · recipiente {slot}\nÁgua: <b>{ml} ml</b>\n{kind}Concluído: {time}",
        "extra": "Rega adicional\n",
        "open": "🌱 Abrir minha planta",
        "garden": "🪴 Abrir meu jardim",
    },
    "pl": {
        "started": "🌱 <b>Twoja roślina została posadzona!</b>\n\n{plant}\nPółka {rack} · pojemnik {slot}\nStart: {time}\n\nBędziemy też informować o każdym podlewaniu.",
        "ready": "🌿 <b>Twoja roślina jest gotowa!</b>\n\n{plant}\nPółka {rack} · pojemnik {slot}\nGotowa: {time}\n\nEtap wzrostu został zakończony i zaplanowane podlewanie zostało zatrzymane. Roślina jest gotowa do zbioru.",
        "harvested": "✅ <b>Cykl uprawy zakończony</b>\n\n{plant}\nPółka {rack} · pojemnik {slot}\nZebrano: {time}\n\nDziękujemy za uprawę z KisaMore!",
        "watered": "💧 <b>Twoja roślina została podlana</b>\n\n{plant}\nPółka {rack} · pojemnik {slot}\nWoda: <b>{ml} ml</b>\n{kind}Wykonano: {time}",
        "extra": "Dodatkowe podlewanie\n",
        "open": "🌱 Otwórz moją roślinę",
        "garden": "🪴 Otwórz mój ogród",
    },
    "zh": {
        "started": "🌱 <b>您的植物已经种下！</b>\n\n{plant}\n架子 {rack} · 容器 {slot}\n开始时间：{time}\n\n之后每次浇水完成，我们也会通知您。",
        "ready": "🌿 <b>您的植物已经成熟！</b>\n\n{plant}\n架子 {rack} · 容器 {slot}\n成熟时间：{time}\n\n生长阶段已经结束，计划浇水已停止。植物可以收获了。",
        "harvested": "✅ <b>种植周期已完成</b>\n\n{plant}\n架子 {rack} · 容器 {slot}\n收获时间：{time}\n\n感谢您与 KisaMore 一起种植！",
        "watered": "💧 <b>您的植物已完成浇水</b>\n\n{plant}\n架子 {rack} · 容器 {slot}\n水量：<b>{ml} 毫升</b>\n{kind}完成时间：{time}",
        "extra": "额外浇水\n",
        "open": "🌱 打开我的植物",
        "garden": "🪴 打开我的花园",
    },
}


def user_language(value: str | None) -> str:
    code = (value or "en").lower().replace("_", "-").split("-", 1)[0]
    return code if code in TEXTS else "en"


def plant_name(plant: Plant, lang: str) -> str:
    names = plant.names or {}
    value = names.get(lang) or names.get("en") or names.get("ru")
    if not value:
        value = next((item for item in names.values() if item), plant.code)
    return escape(str(value))


def local_time(value: datetime | None) -> str:
    aware = aware_utc(value)
    if aware is None:
        return "—"
    return aware.astimezone(farm_zone()).strftime("%d.%m.%Y %H:%M")


async def _already_exists(session, event_key: str) -> bool:
    return await session.get(TelegramActivityDelivery, event_key) is not None


async def _queue_planting_event(
    session,
    *,
    planting: Planting,
    plant: Plant,
    slot: RackSlot,
    telegram_user: TelegramUser,
    delivery_kind: str,
    text_key: str,
    event_time: datetime,
    button_key: str,
    callback_data: str,
) -> bool:
    key = f"{delivery_kind}:{planting.id}"
    if await _already_exists(session, key):
        return False
    lang = user_language(telegram_user.language_code)
    text = TEXTS[lang][text_key].format(
        plant=plant_name(plant, lang),
        rack=slot.rack_id,
        slot=slot.slot_number,
        time=local_time(event_time),
    )
    session.add(
        TelegramActivityDelivery(
            event_key=key,
            telegram_user_id=telegram_user.telegram_user_id,
            kind=delivery_kind,
            payload={
                "text": text,
                "button": TEXTS[lang][button_key],
                "callback_data": callback_data,
                "planting_id": planting.id,
            },
            status="pending",
            attempts=0,
            created_at=aware_utc(event_time) or datetime.now(timezone.utc),
        )
    )
    return True


async def discover_activity(session, now: datetime) -> int:
    cutoff = now - timedelta(hours=RECENT_HOURS)
    created = 0

    planting_rows = (
        await session.execute(
            select(Planting, Plant, RackSlot, Allocation, TelegramUser)
            .join(Plant, Plant.id == Planting.plant_id)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .join(Allocation, Allocation.id == Planting.cloud_allocation_id)
            .join(TelegramUser, TelegramUser.marketplace_user_id == Allocation.user_id)
            .where(
                Planting.status.in_(ACTIVE_PLANTING_STATUSES),
                Planting.planted_at >= cutoff,
                TelegramUser.is_active.is_(True),
            )
            .order_by(Planting.planted_at)
        )
    ).all()

    for planting, plant, slot, _allocation, telegram_user in planting_rows:
        if await _queue_planting_event(
            session,
            planting=planting,
            plant=plant,
            slot=slot,
            telegram_user=telegram_user,
            delivery_kind="planting_started",
            text_key="started",
            event_time=aware_utc(planting.planted_at) or now,
            button_key="open",
            callback_data=f"plant:show:{planting.id}:0",
        ):
            created += 1

    ready_rows = (
        await session.execute(
            select(Planting, Plant, RackSlot, Allocation, TelegramUser)
            .join(Plant, Plant.id == Planting.plant_id)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .join(Allocation, Allocation.id == Planting.cloud_allocation_id)
            .join(TelegramUser, TelegramUser.marketplace_user_id == Allocation.user_id)
            .where(
                Planting.status == "ready",
                Planting.observed_at >= cutoff,
                TelegramUser.is_active.is_(True),
            )
            .order_by(Planting.observed_at)
        )
    ).all()

    for planting, plant, slot, _allocation, telegram_user in ready_rows:
        if await _queue_planting_event(
            session,
            planting=planting,
            plant=plant,
            slot=slot,
            telegram_user=telegram_user,
            delivery_kind="planting_ready",
            text_key="ready",
            event_time=aware_utc(planting.observed_at) or now,
            button_key="open",
            callback_data=f"plant:show:{planting.id}:0",
        ):
            created += 1

    harvested_rows = (
        await session.execute(
            select(Planting, Plant, RackSlot, Allocation, TelegramUser)
            .join(Plant, Plant.id == Planting.plant_id)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .join(Allocation, Allocation.id == Planting.cloud_allocation_id)
            .join(TelegramUser, TelegramUser.marketplace_user_id == Allocation.user_id)
            .where(
                Planting.status == "harvested",
                TelegramUser.is_active.is_(True),
            )
            .order_by(Planting.actual_harvest_at, Planting.observed_at)
        )
    ).all()

    for planting, plant, slot, _allocation, telegram_user in harvested_rows:
        event_time = aware_utc(planting.actual_harvest_at) or aware_utc(planting.observed_at) or now
        if event_time < cutoff:
            continue
        if await _queue_planting_event(
            session,
            planting=planting,
            plant=plant,
            slot=slot,
            telegram_user=telegram_user,
            delivery_kind="planting_harvested",
            text_key="harvested",
            event_time=event_time,
            button_key="garden",
            callback_data="menu:garden",
        ):
            created += 1

    watering_rows = (
        await session.execute(
            select(WateringTask, Planting, Plant, Allocation, TelegramUser)
            .join(Planting, Planting.id == WateringTask.planting_id)
            .join(Plant, Plant.id == Planting.plant_id)
            .join(Allocation, Allocation.id == WateringTask.allocation_id)
            .join(TelegramUser, TelegramUser.marketplace_user_id == Allocation.user_id)
            .where(
                WateringTask.status == "done",
                WateringTask.completed_at.is_not(None),
                WateringTask.completed_at >= cutoff,
                TelegramUser.is_active.is_(True),
            )
            .order_by(WateringTask.completed_at)
        )
    ).all()

    for task, planting, plant, _allocation, telegram_user in watering_rows:
        key = f"watering_done:{task.id}"
        if await _already_exists(session, key):
            continue
        lang = user_language(telegram_user.language_code)
        kind = TEXTS[lang]["extra"] if task.task_type == "extra" else ""
        text = TEXTS[lang]["watered"].format(
            plant=plant_name(plant, lang),
            rack=task.rack_id,
            slot=task.slot_number,
            ml=int(task.actual_ml or task.planned_ml),
            kind=kind,
            time=local_time(task.completed_at),
        )
        session.add(
            TelegramActivityDelivery(
                event_key=key,
                telegram_user_id=telegram_user.telegram_user_id,
                kind="watering_done",
                payload={
                    "text": text,
                    "button": TEXTS[lang]["open"],
                    "callback_data": f"plant:show:{planting.id}:0",
                    "planting_id": planting.id,
                    "watering_task_id": task.id,
                },
                status="pending",
                attempts=0,
                created_at=aware_utc(task.completed_at) or now,
            )
        )
        created += 1

    if created:
        await session.commit()
    return created


async def send_pending(bot: TelegramBotAPI) -> tuple[int, int]:
    sent = 0
    failed = 0
    async with SessionLocal() as session:
        deliveries = list(
            (
                await session.execute(
                    select(TelegramActivityDelivery)
                    .where(
                        TelegramActivityDelivery.status == "pending",
                        TelegramActivityDelivery.attempts < MAX_ATTEMPTS,
                    )
                    .order_by(TelegramActivityDelivery.created_at)
                    .limit(50)
                )
            ).scalars().all()
        )

        for delivery in deliveries:
            payload = delivery.payload or {}
            markup = None
            if payload.get("callback_data"):
                markup = {
                    "inline_keyboard": [[
                        {
                            "text": str(payload.get("button") or "🌱 KisaMore")[:60],
                            "callback_data": str(payload["callback_data"])[:64],
                        }
                    ]]
                }
            try:
                await bot.send_message(
                    delivery.telegram_user_id,
                    str(payload.get("text") or "KisaMore"),
                    reply_markup=markup,
                )
                delivery.status = "sent"
                delivery.sent_at = datetime.now(timezone.utc)
                delivery.last_error = None
                sent += 1
            except Exception as exc:
                delivery.attempts += 1
                delivery.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                if delivery.attempts >= MAX_ATTEMPTS:
                    delivery.status = "failed"
                failed += 1
                logger.exception(
                    "Could not send %s to Telegram user %s",
                    delivery.kind,
                    delivery.telegram_user_id,
                )
            await session.commit()
    return sent, failed


async def run() -> None:
    token = os.getenv("KISAMORE_TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("KISAMORE_TELEGRAM_BOT_TOKEN is not configured")

    await create_tables()
    bot = TelegramBotAPI(token)
    logger.info(
        "KisaMore Telegram activity notifier started: check=%ss recent=%sh",
        CHECK_SECONDS,
        RECENT_HOURS,
    )

    try:
        while True:
            try:
                now = datetime.now(timezone.utc)
                async with SessionLocal() as session:
                    discovered = await discover_activity(session, now)
                sent, failed = await send_pending(bot)
                if discovered or sent or failed:
                    logger.info(
                        "Telegram activity pass: discovered=%s sent=%s failed=%s",
                        discovered,
                        sent,
                        failed,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telegram activity notification pass failed")
            await asyncio.sleep(CHECK_SECONDS)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
