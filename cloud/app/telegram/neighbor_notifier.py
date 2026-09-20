from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..models import Allocation, Plant, Planting, RackPhoto, RackSlot
from .activity_notifier import TelegramActivityDelivery
from .models import TelegramUser
from .neighbor_models import TelegramNeighborDelivery, TelegramNeighborNotifierState
from .service import language_base, localized_value, resolve_photo_path


CHECK_SECONDS = 5
MAX_ATTEMPTS = 5
PHOTO_WAIT_HOURS = 24
ACTIVE_PLANTING_STATUSES = ("planned", "growing", "ready")

logger = logging.getLogger(__name__)

TEXTS = {
    "en": (
        "🌱 <b>A new neighbor appeared on your rack!</b>\n\n"
        "🟢 Your plant(s)\n"
        "🟡 New neighbor — <b>{plant}</b>\n"
        "Rack {rack} · Container {slot}\n\n"
        "The new plant's card is below."
    ),
    "ru": (
        "🌱 <b>На вашей полке появился новый сосед!</b>\n\n"
        "🟢 Ваши растения\n"
        "🟡 Новый сосед — <b>{plant}</b>\n"
        "Полка {rack} · контейнер {slot}\n\n"
        "Ниже — карточка нового растения."
    ),
    "de": (
        "🌱 <b>Auf deinem Regal gibt es einen neuen Nachbarn!</b>\n\n"
        "🟢 Deine Pflanze(n)\n"
        "🟡 Neuer Nachbar — <b>{plant}</b>\n"
        "Regal {rack} · Behälter {slot}\n\n"
        "Unten findest du die Karte der neuen Pflanze."
    ),
    "fr": (
        "🌱 <b>Un nouveau voisin est arrivé sur votre étagère !</b>\n\n"
        "🟢 Votre/vos plante(s)\n"
        "🟡 Nouveau voisin — <b>{plant}</b>\n"
        "Étagère {rack} · bac {slot}\n\n"
        "La fiche de la nouvelle plante se trouve ci-dessous."
    ),
    "es": (
        "🌱 <b>¡Hay un nuevo vecino en tu estante!</b>\n\n"
        "🟢 Tu(s) planta(s)\n"
        "🟡 Nuevo vecino — <b>{plant}</b>\n"
        "Estante {rack} · contenedor {slot}\n\n"
        "Debajo está la ficha de la nueva planta."
    ),
    "it": (
        "🌱 <b>C'è un nuovo vicino sul tuo scaffale!</b>\n\n"
        "🟢 Le tue piante\n"
        "🟡 Nuovo vicino — <b>{plant}</b>\n"
        "Scaffale {rack} · contenitore {slot}\n\n"
        "Sotto trovi la scheda della nuova pianta."
    ),
    "pt": (
        "🌱 <b>Há um novo vizinho na sua prateleira!</b>\n\n"
        "🟢 Sua(s) planta(s)\n"
        "🟡 Novo vizinho — <b>{plant}</b>\n"
        "Prateleira {rack} · recipiente {slot}\n\n"
        "A ficha da nova planta está abaixo."
    ),
    "pl": (
        "🌱 <b>Na Twojej półce pojawił się nowy sąsiad!</b>\n\n"
        "🟢 Twoje rośliny\n"
        "🟡 Nowy sąsiad — <b>{plant}</b>\n"
        "Półka {rack} · pojemnik {slot}\n\n"
        "Poniżej znajduje się karta nowej rośliny."
    ),
    "zh": (
        "🌱 <b>您的架子上来了一个新邻居！</b>\n\n"
        "🟢 您的植物\n"
        "🟡 新邻居 — <b>{plant}</b>\n"
        "架子 {rack} · 容器 {slot}\n\n"
        "下面是新植物的卡片。"
    ),
}

READY_TEXTS = {
    "en": (
        "🌿 <b>A neighbor on your rack is ready!</b>\n\n"
        "🟢 Your plant(s)\n"
        "🟡 Ready for harvest — <b>{plant}</b>\n"
        "Rack {rack} · Container {slot}\n\n"
        "Look how much your neighbor has grown."
    ),
    "ru": (
        "🌿 <b>Сосед на вашей полке уже готов!</b>\n\n"
        "🟢 Ваши растения\n"
        "🟡 Готов к сбору — <b>{plant}</b>\n"
        "Полка {rack} · контейнер {slot}\n\n"
        "Посмотрите, как вырос ваш сосед."
    ),
    "de": (
        "🌿 <b>Ein Nachbar auf deinem Regal ist bereit!</b>\n\n"
        "🟢 Deine Pflanze(n)\n"
        "🟡 Erntereif — <b>{plant}</b>\n"
        "Regal {rack} · Behälter {slot}\n\n"
        "Sieh dir an, wie dein Nachbar gewachsen ist."
    ),
    "fr": (
        "🌿 <b>Un voisin sur votre étagère est prêt !</b>\n\n"
        "🟢 Votre/vos plante(s)\n"
        "🟡 Prêt à récolter — <b>{plant}</b>\n"
        "Étagère {rack} · bac {slot}\n\n"
        "Regardez comme votre voisin a grandi."
    ),
    "es": (
        "🌿 <b>¡Un vecino de tu estante ya está listo!</b>\n\n"
        "🟢 Tu(s) planta(s)\n"
        "🟡 Listo para cosechar — <b>{plant}</b>\n"
        "Estante {rack} · contenedor {slot}\n\n"
        "Mira cuánto ha crecido tu vecino."
    ),
    "it": (
        "🌿 <b>Un vicino sul tuo scaffale è pronto!</b>\n\n"
        "🟢 Le tue piante\n"
        "🟡 Pronto per la raccolta — <b>{plant}</b>\n"
        "Scaffale {rack} · contenitore {slot}\n\n"
        "Guarda quanto è cresciuto il tuo vicino."
    ),
    "pt": (
        "🌿 <b>Um vizinho na sua prateleira está pronto!</b>\n\n"
        "🟢 Sua(s) planta(s)\n"
        "🟡 Pronto para colher — <b>{plant}</b>\n"
        "Prateleira {rack} · recipiente {slot}\n\n"
        "Veja como seu vizinho cresceu."
    ),
    "pl": (
        "🌿 <b>Sąsiad na Twojej półce jest już gotowy!</b>\n\n"
        "🟢 Twoje rośliny\n"
        "🟡 Gotowy do zbioru — <b>{plant}</b>\n"
        "Półka {rack} · pojemnik {slot}\n\n"
        "Zobacz, jak urósł Twój sąsiad."
    ),
    "zh": (
        "🌿 <b>您架子上的邻居已经成熟了！</b>\n\n"
        "🟢 您的植物\n"
        "🟡 可以收获 — <b>{plant}</b>\n"
        "架子 {rack} · 容器 {slot}\n\n"
        "看看您的邻居长大了多少。"
    ),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _language(value: str | None) -> str:
    code = language_base(value)
    return code if code in TEXTS else "en"


def _grid_box(width: int, height: int, slot_number: int) -> tuple[int, int, int, int]:
    slot = int(slot_number)
    if slot < 1 or slot > 6:
        raise ValueError("slot_number must be 1..6")
    index = slot - 1
    row = index // 2
    column = index % 2
    return (
        round(width * column / 2),
        round(height * row / 3),
        round(width * (column + 1) / 2),
        round(height * (row + 1) / 3),
    )


def _visual_box(width: int, height: int, slot_number: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = _grid_box(width, height, slot_number)
    inset = max(5, round(min(right - left, bottom - top) * 0.025))
    return left + inset, top + inset, right - inset, bottom - inset


def _annotate_rack_photo(
    source: Path,
    target: Path,
    *,
    own_slots: list[int],
    new_slot: int,
) -> None:
    from PIL import Image, ImageDraw, ImageOps

    with Image.open(source) as opened:
        opened.load()
        image = ImageOps.exif_transpose(opened).convert("RGB")

    width, height = image.size
    line_width = max(5, round(min(width, height) * 0.009))
    radius = max(10, round(min(width, height) * 0.02))
    draw = ImageDraw.Draw(image)

    for slot_number in sorted(set(int(value) for value in own_slots)):
        draw.rounded_rectangle(
            _visual_box(width, height, slot_number),
            radius=radius,
            outline=(34, 197, 94),
            width=line_width,
        )

    draw.rounded_rectangle(
        _visual_box(width, height, int(new_slot)),
        radius=radius,
        outline=(250, 190, 20),
        width=line_width,
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    image.save(temporary, format="JPEG", quality=93, optimize=True)
    temporary.replace(target)


async def _ensure_activation(session) -> TelegramNeighborNotifierState | None:
    state = await session.get(TelegramNeighborNotifierState, 1)
    if state is not None:
        return state

    state = TelegramNeighborNotifierState(id=1, activated_at=_now())
    session.add(state)
    await session.commit()
    logger.info(
        "Telegram neighbor notifications activated at %s; existing plantings are ignored",
        state.activated_at,
    )
    return None


async def discover_neighbor_deliveries() -> int:
    created = 0
    async with SessionLocal() as session:
        state = await _ensure_activation(session)
        if state is None:
            return 0

        planting_rows = (
            await session.execute(
                select(Planting, Plant, RackSlot, Allocation)
                .join(Plant, Plant.id == Planting.plant_id)
                .join(RackSlot, RackSlot.id == Planting.slot_id)
                .join(Allocation, Allocation.id == Planting.cloud_allocation_id)
                .where(
                    Planting.status.in_(ACTIVE_PLANTING_STATUSES),
                    Planting.planted_at >= state.activated_at,
                    Allocation.status == "active",
                )
                .order_by(Planting.planted_at)
                .limit(200)
            )
        ).all()

        for planting, _plant, slot, owner_allocation in planting_rows:
            recipients = list(
                (
                    await session.execute(
                        select(TelegramUser)
                        .join(
                            Allocation,
                            TelegramUser.marketplace_user_id == Allocation.user_id,
                        )
                        .where(
                            Allocation.device_id == slot.device_id,
                            Allocation.rack_id == slot.rack_id,
                            Allocation.status == "active",
                            Allocation.slot_number.is_not(None),
                            Allocation.user_id != owner_allocation.user_id,
                            TelegramUser.is_active.is_(True),
                        )
                        .distinct()
                    )
                ).scalars().all()
            )
            for recipient in recipients:
                exists = (
                    await session.execute(
                        select(TelegramNeighborDelivery.id)
                        .where(
                            TelegramNeighborDelivery.planting_id == planting.id,
                            TelegramNeighborDelivery.user_id == recipient.id,
                        )
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if exists is not None:
                    continue

                session.add(
                    TelegramNeighborDelivery(
                        planting_id=planting.id,
                        user_id=recipient.id,
                        status="pending",
                        attempts=0,
                        created_at=_aware(planting.planted_at) or _now(),
                    )
                )
                created += 1

        if created:
            await session.commit()
    return created


async def _ready_recipients(
    session,
    slot: RackSlot,
    owner_allocation: Allocation,
    *,
    event_at: datetime | None = None,
) -> list[TelegramUser]:
    conditions = [
        Allocation.device_id == slot.device_id,
        Allocation.rack_id == slot.rack_id,
        Allocation.status == "active",
        Allocation.slot_number.is_not(None),
        Allocation.user_id != owner_allocation.user_id,
        TelegramUser.is_active.is_(True),
    ]
    if event_at is not None:
        conditions.append(Allocation.starts_at <= event_at)

    return list(
        (
            await session.execute(
                select(TelegramUser)
                .join(
                    Allocation,
                    TelegramUser.marketplace_user_id == Allocation.user_id,
                )
                .where(*conditions)
                .distinct()
            )
        ).scalars().all()
    )


async def _ensure_ready_activation(session) -> TelegramNeighborNotifierState | None:
    state = await session.get(TelegramNeighborNotifierState, 2)
    if state is not None:
        return state

    state = TelegramNeighborNotifierState(id=2, activated_at=_now())
    session.add(state)
    await session.commit()
    logger.info(
        "Telegram ready-neighbor notifications activated at %s; existing ready plantings are ignored",
        state.activated_at,
    )
    return None


async def discover_ready_neighbor_deliveries() -> int:
    """Reuse the existing neighbor delivery row for the later ready event.

    The table has a unique (planting_id, user_id) key from the original
    new-neighbor feature. Instead of creating another table, a successfully
    completed planting notification is advanced to a ready_* state when the
    same planting becomes ready. This preserves the existing schema on VPS.
    """
    changed = 0
    async with SessionLocal() as session:
        state = await _ensure_ready_activation(session)
        if state is None:
            return 0

        rows = (
            await session.execute(
                select(Planting, RackSlot, Allocation)
                .join(RackSlot, RackSlot.id == Planting.slot_id)
                .join(Allocation, Allocation.id == Planting.cloud_allocation_id)
                .where(
                    Planting.status == "ready",
                    Allocation.status == "active",
                )
                .order_by(Planting.observed_at)
                .limit(200)
            )
        ).all()

        for planting, slot, owner_allocation in rows:
            ready_event = await session.get(
                TelegramActivityDelivery,
                f"planting_ready:{planting.id}",
            )
            if ready_event is None:
                # The lifecycle notifier has not recorded the stable ready
                # transition yet. Retry on the next pass.
                continue

            event_at = _aware(ready_event.created_at) or _now()
            activated_at = _aware(state.activated_at) or event_at
            if event_at < activated_at:
                continue

            recipients = await _ready_recipients(
                session,
                slot,
                owner_allocation,
                event_at=event_at,
            )
            for recipient in recipients:
                delivery = (
                    await session.execute(
                        select(TelegramNeighborDelivery)
                        .where(
                            TelegramNeighborDelivery.planting_id == planting.id,
                            TelegramNeighborDelivery.user_id == recipient.id,
                        )
                        .limit(1)
                    )
                ).scalar_one_or_none()

                if delivery is not None and str(delivery.status).startswith("ready_"):
                    continue

                # If the original new-neighbor message is still being sent,
                # let it finish first. A later pass will promote this same row.
                if delivery is not None and delivery.status in ("pending", "sending"):
                    continue

                if delivery is None:
                    delivery = TelegramNeighborDelivery(
                        planting_id=planting.id,
                        user_id=recipient.id,
                        status="ready_pending",
                        attempts=0,
                        created_at=event_at,
                    )
                    session.add(delivery)
                else:
                    delivery.status = "ready_pending"
                    delivery.attempts = 0
                    delivery.last_error = None
                    delivery.annotated_photo_path = None
                    delivery.photo_sent_at = None
                    delivery.card_sent_at = None
                    delivery.created_at = event_at
                    delivery.sent_at = None
                changed += 1

        if changed:
            await session.commit()
    return changed


async def _recipient_slots(
    session,
    telegram_user: TelegramUser,
    *,
    device_id: str,
    rack_id: int,
) -> list[int]:
    if not telegram_user.marketplace_user_id:
        return []
    values = list(
        (
            await session.execute(
                select(Allocation.slot_number).where(
                    Allocation.user_id == telegram_user.marketplace_user_id,
                    Allocation.device_id == device_id,
                    Allocation.rack_id == rack_id,
                    Allocation.status == "active",
                    Allocation.slot_number.is_not(None),
                )
            )
        ).scalars().all()
    )
    return sorted(
        {int(value) for value in values if value is not None and 1 <= int(value) <= 6}
    )


async def _fresh_rack_photo(
    session,
    *,
    slot: RackSlot,
    planted_at: datetime,
) -> tuple[RackPhoto | None, Path | None]:
    photo = (
        await session.execute(
            select(RackPhoto).where(
                RackPhoto.device_id == slot.device_id,
                RackPhoto.rack_id == slot.rack_id,
            )
        )
    ).scalar_one_or_none()
    if photo is None:
        return None, None

    planted = _aware(planted_at) or _now()
    captured = _aware(photo.captured_at)
    updated = _aware(photo.updated_at)

    fresh = captured is not None and captured >= planted
    if not fresh and _now() - planted >= timedelta(minutes=10):
        fresh = updated is not None and updated >= planted
    if not fresh:
        return photo, None

    return photo, resolve_photo_path(photo)


def _target_path(planting_id: str, telegram_user_id: int) -> Path:
    return (
        Path(get_settings().photo_dir)
        / "telegram"
        / "neighbors"
        / planting_id
        / f"user_{int(telegram_user_id)}.jpg"
    )


async def _mark_error(session, delivery: TelegramNeighborDelivery, exc: Exception) -> None:
    delivery.attempts += 1
    delivery.last_error = f"{type(exc).__name__}: {exc}"[:2000]
    if delivery.attempts >= MAX_ATTEMPTS:
        delivery.status = "failed"
    await session.commit()


async def _send_delivery(bot, core, delivery_id: int) -> bool:
    async with SessionLocal() as session:
        delivery = await session.get(TelegramNeighborDelivery, delivery_id)
        if delivery is None or delivery.status not in ("pending", "sending"):
            return False

        row = (
            await session.execute(
                select(Planting, Plant, RackSlot)
                .join(Plant, Plant.id == Planting.plant_id)
                .join(RackSlot, RackSlot.id == Planting.slot_id)
                .where(Planting.id == delivery.planting_id)
                .limit(1)
            )
        ).first()
        telegram_user = await session.get(TelegramUser, delivery.user_id)
        if row is None or telegram_user is None or not telegram_user.is_active:
            delivery.status = "ready_skipped"
            delivery.last_error = "Planting or active Telegram user is no longer available"
            await session.commit()
            return False

        planting, plant, slot = row
        if planting.status not in ACTIVE_PLANTING_STATUSES:
            delivery.status = "skipped"
            delivery.last_error = "Planting is no longer active"
            await session.commit()
            return False

        own_slots = await _recipient_slots(
            session,
            telegram_user,
            device_id=slot.device_id,
            rack_id=slot.rack_id,
        )
        if not own_slots:
            delivery.status = "ready_skipped"
            delivery.last_error = "Recipient no longer has an active plant on this rack"
            await session.commit()
            return False

        card = await core.get_plant_card(planting.id, telegram_user.id)
        if card is None:
            delivery.status = "skipped"
            delivery.last_error = "New plant card is no longer available"
            await session.commit()
            return False

        if delivery.photo_sent_at is None:
            _photo, source = await _fresh_rack_photo(
                session,
                slot=slot,
                planted_at=planting.planted_at,
            )
            if source is None:
                created_at = _aware(delivery.created_at) or _now()
                if _now() - created_at >= timedelta(hours=PHOTO_WAIT_HOURS):
                    delivery.status = "skipped"
                    delivery.last_error = "No fresh rack photo arrived within 24 hours"
                    await session.commit()
                return False

            target = _target_path(planting.id, telegram_user.telegram_user_id)
            try:
                _annotate_rack_photo(
                    source,
                    target,
                    own_slots=own_slots,
                    new_slot=slot.slot_number,
                )
                lang = _language(telegram_user.language_code)
                name = escape(localized_value(plant.names, lang, plant.code))
                caption = TEXTS[lang].format(
                    plant=name,
                    rack=slot.rack_id,
                    slot=slot.slot_number,
                )
                await bot.send_photo(
                    telegram_user.telegram_user_id,
                    target,
                    caption=caption,
                )
            except Exception as exc:
                logger.exception(
                    "Could not send new-neighbor rack photo for planting %s to Telegram user %s",
                    planting.id,
                    telegram_user.telegram_user_id,
                )
                await _mark_error(session, delivery, exc)
                return False

            delivery.annotated_photo_path = str(target)
            delivery.photo_sent_at = _now()
            delivery.status = "ready_sending"
            delivery.last_error = None
            await session.commit()

        if delivery.card_sent_at is None:
            tg = {
                "id": telegram_user.telegram_user_id,
                "username": telegram_user.username,
                "first_name": telegram_user.first_name,
                "last_name": telegram_user.last_name,
                "language_code": telegram_user.language_code,
            }
            try:
                await core.show_plant_card(
                    bot,
                    telegram_user.telegram_user_id,
                    tg,
                    planting.id,
                    index=0,
                    total=1,
                    user_id=telegram_user.id,
                )
            except Exception as exc:
                logger.exception(
                    "Could not send new-neighbor plant card for planting %s to Telegram user %s",
                    planting.id,
                    telegram_user.telegram_user_id,
                )
                await _mark_error(session, delivery, exc)
                return False

            delivery.card_sent_at = _now()

        delivery.status = "sent"
        delivery.sent_at = _now()
        delivery.last_error = None
        await session.commit()
        return True


def _ready_target_path(planting_id: str, telegram_user_id: int) -> Path:
    return (
        Path(get_settings().photo_dir)
        / "telegram"
        / "neighbors_ready"
        / planting_id
        / f"user_{int(telegram_user_id)}.jpg"
    )


async def _mark_ready_error(session, delivery: TelegramNeighborDelivery, exc: Exception) -> None:
    delivery.attempts += 1
    delivery.last_error = f"{type(exc).__name__}: {exc}"[:2000]
    if delivery.attempts >= MAX_ATTEMPTS:
        delivery.status = "ready_failed"
    await session.commit()


async def _send_ready_delivery(bot, core, delivery_id: int) -> bool:
    async with SessionLocal() as session:
        delivery = await session.get(TelegramNeighborDelivery, delivery_id)
        if delivery is None or delivery.status not in ("ready_pending", "ready_sending"):
            return False

        row = (
            await session.execute(
                select(Planting, Plant, RackSlot)
                .join(Plant, Plant.id == Planting.plant_id)
                .join(RackSlot, RackSlot.id == Planting.slot_id)
                .where(Planting.id == delivery.planting_id)
                .limit(1)
            )
        ).first()
        telegram_user = await session.get(TelegramUser, delivery.user_id)
        if row is None or telegram_user is None or not telegram_user.is_active:
            delivery.status = "skipped"
            delivery.last_error = "Planting or active Telegram user is no longer available"
            await session.commit()
            return False

        planting, plant, slot = row
        if planting.status != "ready":
            delivery.status = "ready_skipped"
            delivery.last_error = "Planting is no longer in ready state"
            await session.commit()
            return False

        own_slots = await _recipient_slots(
            session,
            telegram_user,
            device_id=slot.device_id,
            rack_id=slot.rack_id,
        )
        if not own_slots:
            delivery.status = "skipped"
            delivery.last_error = "Recipient no longer has an active plant on this rack"
            await session.commit()
            return False

        card = await core.get_plant_card(planting.id, telegram_user.id)
        if card is None:
            delivery.status = "ready_skipped"
            delivery.last_error = "Ready plant card is no longer available"
            await session.commit()
            return False

        if delivery.photo_sent_at is None:
            _photo, source = await _fresh_rack_photo(
                session,
                slot=slot,
                planted_at=delivery.created_at,
            )
            if source is None:
                created_at = _aware(delivery.created_at) or _now()
                if _now() - created_at >= timedelta(hours=PHOTO_WAIT_HOURS):
                    delivery.status = "ready_skipped"
                    delivery.last_error = "No fresh rack photo arrived within 24 hours of ready event"
                    await session.commit()
                return False

            target = _ready_target_path(planting.id, telegram_user.telegram_user_id)
            try:
                _annotate_rack_photo(
                    source,
                    target,
                    own_slots=own_slots,
                    new_slot=slot.slot_number,
                )
                lang = _language(telegram_user.language_code)
                name = escape(localized_value(plant.names, lang, plant.code))
                caption = READY_TEXTS[lang].format(
                    plant=name,
                    rack=slot.rack_id,
                    slot=slot.slot_number,
                )
                await bot.send_photo(
                    telegram_user.telegram_user_id,
                    target,
                    caption=caption,
                )
            except Exception as exc:
                logger.exception(
                    "Could not send ready-neighbor rack photo for planting %s to Telegram user %s",
                    planting.id,
                    telegram_user.telegram_user_id,
                )
                await _mark_ready_error(session, delivery, exc)
                return False

            delivery.annotated_photo_path = str(target)
            delivery.photo_sent_at = _now()
            delivery.status = "sending"
            delivery.last_error = None
            await session.commit()

        if delivery.card_sent_at is None:
            tg = {
                "id": telegram_user.telegram_user_id,
                "username": telegram_user.username,
                "first_name": telegram_user.first_name,
                "last_name": telegram_user.last_name,
                "language_code": telegram_user.language_code,
            }
            try:
                await core.show_plant_card(
                    bot,
                    telegram_user.telegram_user_id,
                    tg,
                    planting.id,
                    index=0,
                    total=1,
                    user_id=telegram_user.id,
                )
            except Exception as exc:
                logger.exception(
                    "Could not send ready-neighbor plant card for planting %s to Telegram user %s",
                    planting.id,
                    telegram_user.telegram_user_id,
                )
                await _mark_ready_error(session, delivery, exc)
                return False

            delivery.card_sent_at = _now()

        delivery.status = "ready_sent"
        delivery.sent_at = _now()
        delivery.last_error = None
        await session.commit()
        return True


async def neighbor_notification_loop(bot, core) -> None:
    while True:
        try:
            created = await discover_neighbor_deliveries()
            ready_created = await discover_ready_neighbor_deliveries()
            async with SessionLocal() as session:
                delivery_ids = list(
                    (
                        await session.execute(
                            select(TelegramNeighborDelivery.id)
                            .where(
                                TelegramNeighborDelivery.status.in_(("pending", "sending")),
                                TelegramNeighborDelivery.attempts < MAX_ATTEMPTS,
                            )
                            .order_by(TelegramNeighborDelivery.created_at)
                            .limit(20)
                        )
                    ).scalars().all()
                )
                ready_delivery_ids = list(
                    (
                        await session.execute(
                            select(TelegramNeighborDelivery.id)
                            .where(
                                TelegramNeighborDelivery.status.in_(("ready_pending", "ready_sending")),
                                TelegramNeighborDelivery.attempts < MAX_ATTEMPTS,
                            )
                            .order_by(TelegramNeighborDelivery.created_at)
                            .limit(20)
                        )
                    ).scalars().all()
                )

            sent = 0
            for delivery_id in delivery_ids:
                if await _send_delivery(bot, core, delivery_id):
                    sent += 1
                await asyncio.sleep(0.08)

            ready_sent = 0
            for delivery_id in ready_delivery_ids:
                if await _send_ready_delivery(bot, core, delivery_id):
                    ready_sent += 1
                await asyncio.sleep(0.08)

            if created or ready_created or sent or ready_sent:
                logger.info(
                    "Telegram neighbor notification pass: planted_created=%s planted_sent=%s "
                    "ready_created=%s ready_sent=%s pending=%s ready_pending=%s",
                    created,
                    sent,
                    ready_created,
                    ready_sent,
                    len(delivery_ids),
                    len(ready_delivery_ids),
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram neighbor notification pass failed")
        await asyncio.sleep(CHECK_SECONDS)


def install(core) -> None:
    previous_follow_notification_loop = core.follow_notification_loop

    async def follow_notification_loop(bot) -> None:
        await asyncio.gather(
            previous_follow_notification_loop(bot),
            neighbor_notification_loop(bot, core),
        )

    core.follow_notification_loop = follow_notification_loop
