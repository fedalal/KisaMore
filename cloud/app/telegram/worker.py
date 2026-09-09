from __future__ import annotations

import asyncio
from html import escape

from sqlalchemy import select

from ..admin_models import PlantingPhoto
from ..db import SessionLocal
from ..models import Plant
from . import worker_core as core
from .rental_service import InsufficientRentalBalance, create_rental_request, list_available_slots


_original_get_plant_card = core.get_plant_card
_original_handle_callback = core.handle_callback


RENT_TEXT = {
    "en": {
        "active": "🪴 <b>Active rentals</b>",
        "allocation": "• {plant} · Rack {rack} · Container {slot}",
        "insufficient": "Not enough Kisa for this rental. Price: {price} Kisa. Balance: {balance} Kisa.",
        "charged": "✅ Rental request created. {price} Kisa deducted. If the request is rejected, the amount will be refunded.",
    },
    "ru": {
        "active": "🪴 <b>Активные аренды</b>",
        "allocation": "• {plant} · Полка {rack} · Контейнер {slot}",
        "insufficient": "Недостаточно Kisa для аренды. Цена: {price} Kisa. Баланс: {balance} Kisa.",
        "charged": "✅ Заявка на аренду создана. Списано {price} Kisa. Если заявку отклонят, сумма будет возвращена.",
    },
    "de": {
        "active": "🪴 <b>Aktive Mieten</b>",
        "allocation": "• {plant} · Regal {rack} · Behälter {slot}",
        "insufficient": "Nicht genug Kisa. Preis: {price} Kisa. Guthaben: {balance} Kisa.",
        "charged": "✅ Mietanfrage erstellt. {price} Kisa wurden abgezogen. Bei Ablehnung werden sie zurückerstattet.",
    },
    "fr": {
        "active": "🪴 <b>Locations actives</b>",
        "allocation": "• {plant} · Étagère {rack} · Bac {slot}",
        "insufficient": "Pas assez de Kisa. Prix : {price} Kisa. Solde : {balance} Kisa.",
        "charged": "✅ Demande créée. {price} Kisa débités. En cas de refus, ils seront remboursés.",
    },
    "es": {
        "active": "🪴 <b>Alquileres activos</b>",
        "allocation": "• {plant} · Estante {rack} · Contenedor {slot}",
        "insufficient": "No tienes suficientes Kisa. Precio: {price} Kisa. Saldo: {balance} Kisa.",
        "charged": "✅ Solicitud creada. Se descontaron {price} Kisa. Si se rechaza, se reembolsarán.",
    },
    "it": {
        "active": "🪴 <b>Noleggi attivi</b>",
        "allocation": "• {plant} · Scaffale {rack} · Contenitore {slot}",
        "insufficient": "Kisa insufficienti. Prezzo: {price} Kisa. Saldo: {balance} Kisa.",
        "charged": "✅ Richiesta creata. Addebitati {price} Kisa. In caso di rifiuto saranno rimborsati.",
    },
    "pt": {
        "active": "🪴 <b>Aluguéis ativos</b>",
        "allocation": "• {plant} · Prateleira {rack} · Recipiente {slot}",
        "insufficient": "Kisa insuficientes. Preço: {price} Kisa. Saldo: {balance} Kisa.",
        "charged": "✅ Pedido criado. {price} Kisa debitados. Se for rejeitado, serão devolvidos.",
    },
    "pl": {
        "active": "🪴 <b>Aktywne wynajmy</b>",
        "allocation": "• {plant} · Półka {rack} · Pojemnik {slot}",
        "insufficient": "Za mało Kisa. Cena: {price} Kisa. Saldo: {balance} Kisa.",
        "charged": "✅ Wniosek utworzony. Pobrano {price} Kisa. Po odrzuceniu kwota zostanie zwrócona.",
    },
    "zh": {
        "active": "🪴 <b>有效租用</b>",
        "allocation": "• {plant} · 架子 {rack} · 容器 {slot}",
        "insufficient": "Kisa 余额不足。价格：{price} Kisa。余额：{balance} Kisa。",
        "charged": "✅ 租用申请已创建，已扣除 {price} Kisa。如申请被拒绝，金额将退回。",
    },
}


def rt(lang: str, key: str, **kwargs) -> str:
    locale = RENT_TEXT.get(lang) or RENT_TEXT["en"]
    return (locale.get(key) or RENT_TEXT["en"][key]).format(**kwargs)


async def get_plant_card(planting_id: str, user_id: int):
    """Prefer an admin-published photo for this planting over the generic rack photo."""
    card = await _original_get_plant_card(planting_id, user_id)
    if card is None:
        return None
    async with SessionLocal() as session:
        photo = (
            await session.execute(
                select(PlantingPhoto)
                .where(
                    PlantingPhoto.planting_id == planting_id,
                    PlantingPhoto.is_public.is_(True),
                )
                .order_by(PlantingPhoto.published_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if photo is not None:
        card.photo = photo
    return card


async def show_rental_plants(bot, chat_id: int, tg: dict, slot_id: int) -> None:
    """Show plants sorted by localized name, including the rental price."""
    lang = core.language_for(tg)
    slots = await list_available_slots(50)
    slot = next((item for item in slots if item.id == slot_id), None)
    if slot is None:
        await show_rental_slots(bot, chat_id, tg)
        return

    plants = await core.list_active_plants(50)
    plants.sort(
        key=lambda plant: (
            core.plant_name(plant, lang).casefold(),
            (getattr(plant, "code", "") or "").casefold(),
        )
    )

    rows = [
        [
            {
                "text": f"🌱 {core.plant_name(plant, lang)} · {int(plant.rental_price_kisa or 0)} Kisa"[:60],
                "callback_data": f"rent:plant:{slot_id}:{plant.id}",
            }
        ]
        for plant in plants
    ]
    rows.append(
        [{"text": core.st(lang, "cancel"), "callback_data": "menu:garden"}]
    )
    await bot.send_message(
        chat_id,
        core.st(
            lang,
            "rent_choose_plant",
            rack=slot.rack_id,
            slot=slot.slot_number,
        ),
        reply_markup={"inline_keyboard": rows},
    )


async def show_rental_slots(bot, chat_id: int, tg: dict) -> None:
    """Start rental with the first truly available container."""
    lang = core.language_for(tg)
    slots = await list_available_slots(1)
    if not slots:
        await bot.send_message(
            chat_id,
            core.st(lang, "rent_no_slots"),
            reply_markup={
                "inline_keyboard": [[
                    {"text": core.st(lang, "back_garden"), "callback_data": "menu:garden"}
                ]]
            },
        )
        return

    await show_rental_plants(bot, chat_id, tg, slots[0].id)


async def show_garden(bot, chat_id: int, tg: dict) -> None:
    """Render My Garden completely in the user's language."""
    lang = core.language_for(tg)
    user, _ = await core.get_or_create_user(tg)
    followed = await core.list_followed_plantings(user.id, 6)
    requests = await core.rental_requests(user.id, 6)
    allocations = await core.linked_allocations(user, 6)
    parts = [core.t(lang, "garden")]
    buttons = []

    if followed:
        parts.append("\n" + core.st(lang, "garden_following"))
        for planting, plant, slot in followed:
            name = core.plant_name(plant, lang)
            parts.append(f"• 🌱 {escape(name)} · #{slot.rack_id}/{slot.slot_number}")
            buttons.append([{"text": f"🌱 {name}"[:60], "callback_data": f"plant:show:{planting.id}:0"}])

    if requests:
        parts.append(core.st(lang, "garden_requests"))
        for req, slot, plant in requests:
            parts.append(
                core.st(
                    lang,
                    "rent_status",
                    rack=slot.rack_id,
                    slot=slot.slot_number,
                    plant=escape(core.plant_name(plant, lang)),
                    status=escape(core.st(lang, f"status_{req.status}")),
                )
            )

    if allocations:
        plant_ids = {item.plant_id for item in allocations if item.plant_id}
        plants_by_id = {}
        if plant_ids:
            async with SessionLocal() as session:
                plant_rows = (
                    await session.execute(select(Plant).where(Plant.id.in_(plant_ids)))
                ).scalars().all()
                plants_by_id = {item.id: item for item in plant_rows}
        parts.append("\n" + rt(lang, "active"))
        for allocation in allocations:
            plant = plants_by_id.get(allocation.plant_id)
            name = core.plant_name(plant, lang) if plant else "🌱"
            parts.append(
                rt(
                    lang,
                    "allocation",
                    plant=escape(name),
                    rack=allocation.rack_id,
                    slot=allocation.slot_number or "—",
                )
            )

    if not followed and not requests and not allocations:
        parts.append("\n" + core.st(lang, "garden_empty"))
    buttons.append([{"text": core.st(lang, "rent_button"), "callback_data": "rent:start"}])
    buttons.append([{"text": core.t(lang, "back_home"), "callback_data": "menu:home"}])
    await bot.send_message(chat_id, "\n".join(parts), reply_markup={"inline_keyboard": buttons})


async def handle_callback(bot, query: dict) -> None:
    data = str(query.get("data") or "")
    if not data.startswith("rent:plant:"):
        await _original_handle_callback(bot, query)
        return

    qid = query.get("id")
    tg = query.get("from")
    chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
    if not qid or tg is None or chat_id is None:
        return
    lang = core.language_for(tg)
    parts = data.split(":", 3)
    await bot.answer_callback_query(qid)
    if len(parts) != 4:
        return
    try:
        slot_id = int(parts[2])
    except ValueError:
        return

    user, _ = await core.get_or_create_user(tg)
    try:
        request = await create_rental_request(user.id, slot_id, parts[3])
    except InsufficientRentalBalance as exc:
        await bot.send_message(
            chat_id,
            rt(lang, "insufficient", price=exc.price, balance=exc.balance),
        )
        await show_garden(bot, chat_id, tg)
        return
    except ValueError:
        await bot.send_message(chat_id, core.st(lang, "rent_no_slots"))
        await show_garden(bot, chat_id, tg)
        return

    await bot.send_message(chat_id, rt(lang, "charged", price=request.price_kisa))
    await show_garden(bot, chat_id, tg)


# Functions defined in worker_core resolve globals in that module at runtime.
# Replace only the integration helpers without duplicating the whole worker.
core.get_plant_card = get_plant_card
core.list_available_slots = list_available_slots
core.create_rental_request = create_rental_request
core.show_rental_plants = show_rental_plants
core.show_rental_slots = show_rental_slots
core.show_garden = show_garden
core.handle_callback = handle_callback


if __name__ == "__main__":
    asyncio.run(core.run())
