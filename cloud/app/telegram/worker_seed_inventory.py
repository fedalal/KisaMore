from __future__ import annotations

import asyncio
import os
from html import escape
from pathlib import Path

from sqlalchemy import select

from ..admin_models import PlantingPhoto
from ..db import SessionLocal
from ..models import Plant, Planting
from ..seed_inventory import list_rentable_plants
from . import worker_watering as existing


core = existing.core
_original_handle_callback = core.handle_callback
PLANT_IMAGE_DIR = Path(
    os.getenv("KISAMORE_PLANT_IMAGE_DIR", "/srv/kisamore/data/plant-images")
)

SEED_TEXT = {
    "en": "🌾 There are currently no plants with enough seeds for a new container.",
    "ru": "🌾 Сейчас нет растений с достаточным остатком семян для нового контейнера.",
    "de": "🌾 Zurzeit gibt es keine Pflanzen mit genügend Saatgut für einen neuen Behälter.",
    "fr": "🌾 Il n’y a actuellement aucune plante avec assez de graines pour un nouveau bac.",
    "es": "🌾 Ahora no hay plantas con suficientes semillas para un contenedor nuevo.",
    "it": "🌾 Al momento non ci sono piante con semi sufficienti per un nuovo contenitore.",
    "pt": "🌾 No momento não há plantas com sementes suficientes para um novo recipiente.",
    "pl": "🌾 Obecnie nie ma roślin z wystarczającą ilością nasion na nowy pojemnik.",
    "zh": "🌾 目前没有种子库存足够用于新容器的植物。",
}

RENTAL_INFO_TEXT = {
    "en": {
        "days_short": "d",
        "grow_days": "Growing time",
        "days": "days",
        "price": "Rental price",
        "description": "About this plant",
        "description_empty": "No additional description is available yet.",
        "seed_photo": "Seeds",
        "microgreen_photo": "Ready microgreens",
        "real_photo": "Recent greenhouse photo",
        "no_photo": "A photo of this plant is not available yet.",
        "choose": "✅ Choose this plant",
        "back": "⬅️ Back to plants",
    },
    "ru": {
        "days_short": "дн",
        "grow_days": "Срок выращивания",
        "days": "дней",
        "price": "Стоимость аренды",
        "description": "Описание",
        "description_empty": "Дополнительное описание пока не заполнено.",
        "seed_photo": "Семена",
        "microgreen_photo": "Готовая микрозелень",
        "real_photo": "Свежее фото из теплицы",
        "no_photo": "Фотография этого растения пока не загружена.",
        "choose": "✅ Выбрать это растение",
        "back": "⬅️ К списку растений",
    },
    "de": {
        "days_short": "T",
        "grow_days": "Anbauzeit",
        "days": "Tage",
        "price": "Mietpreis",
        "description": "Beschreibung",
        "description_empty": "Noch keine zusätzliche Beschreibung verfügbar.",
        "seed_photo": "Saatgut",
        "microgreen_photo": "Fertige Microgreens",
        "real_photo": "Aktuelles Gewächshausfoto",
        "no_photo": "Für diese Pflanze ist noch kein Foto verfügbar.",
        "choose": "✅ Diese Pflanze wählen",
        "back": "⬅️ Zur Pflanzenliste",
    },
    "fr": {
        "days_short": "j",
        "grow_days": "Durée de culture",
        "days": "jours",
        "price": "Prix de location",
        "description": "Description",
        "description_empty": "Aucune description supplémentaire pour le moment.",
        "seed_photo": "Graines",
        "microgreen_photo": "Micropousses prêtes",
        "real_photo": "Photo récente de la serre",
        "no_photo": "Aucune photo de cette plante n’est encore disponible.",
        "choose": "✅ Choisir cette plante",
        "back": "⬅️ Retour aux plantes",
    },
    "es": {
        "days_short": "d",
        "grow_days": "Tiempo de cultivo",
        "days": "días",
        "price": "Precio del alquiler",
        "description": "Descripción",
        "description_empty": "Todavía no hay una descripción adicional.",
        "seed_photo": "Semillas",
        "microgreen_photo": "Microbrotes listos",
        "real_photo": "Foto reciente del invernadero",
        "no_photo": "Todavía no hay una foto disponible de esta planta.",
        "choose": "✅ Elegir esta planta",
        "back": "⬅️ Volver a las plantas",
    },
    "it": {
        "days_short": "g",
        "grow_days": "Tempo di coltivazione",
        "days": "giorni",
        "price": "Prezzo del noleggio",
        "description": "Descrizione",
        "description_empty": "Non è ancora disponibile una descrizione aggiuntiva.",
        "seed_photo": "Semi",
        "microgreen_photo": "Microgreens pronti",
        "real_photo": "Foto recente della serra",
        "no_photo": "Non è ancora disponibile una foto di questa pianta.",
        "choose": "✅ Scegli questa pianta",
        "back": "⬅️ Torna alle piante",
    },
    "pt": {
        "days_short": "d",
        "grow_days": "Tempo de cultivo",
        "days": "dias",
        "price": "Preço do aluguel",
        "description": "Descrição",
        "description_empty": "Ainda não há uma descrição adicional.",
        "seed_photo": "Sementes",
        "microgreen_photo": "Microverdes prontos",
        "real_photo": "Foto recente da estufa",
        "no_photo": "Ainda não há uma foto disponível desta planta.",
        "choose": "✅ Escolher esta planta",
        "back": "⬅️ Voltar às plantas",
    },
    "pl": {
        "days_short": "d",
        "grow_days": "Czas uprawy",
        "days": "dni",
        "price": "Cena wynajmu",
        "description": "Opis",
        "description_empty": "Dodatkowy opis nie jest jeszcze dostępny.",
        "seed_photo": "Nasiona",
        "microgreen_photo": "Gotowa mikrozielenina",
        "real_photo": "Najnowsze zdjęcie ze szklarni",
        "no_photo": "Zdjęcie tej rośliny nie jest jeszcze dostępne.",
        "choose": "✅ Wybierz tę roślinę",
        "back": "⬅️ Wróć do roślin",
    },
    "zh": {
        "days_short": "天",
        "grow_days": "生长周期",
        "days": "天",
        "price": "租用价格",
        "description": "介绍",
        "description_empty": "暂时没有更多介绍。",
        "seed_photo": "种子",
        "microgreen_photo": "成熟微型蔬菜",
        "real_photo": "温室近期实拍",
        "no_photo": "暂时没有这种植物的照片。",
        "choose": "✅ 选择这种植物",
        "back": "⬅️ 返回植物列表",
    },
}


def seed_text(lang: str) -> str:
    return SEED_TEXT.get(lang) or SEED_TEXT["en"]


def info_text(lang: str, key: str) -> str:
    values = RENTAL_INFO_TEXT.get(lang) or RENTAL_INFO_TEXT["en"]
    return values.get(key) or RENTAL_INFO_TEXT["en"][key]


def plant_description(plant: Plant, lang: str) -> str:
    return core.localized_value(
        getattr(plant, "descriptions", None),
        lang,
        "",
    )


def _catalog_image(raw_name: str | None) -> str | None:
    """Resolve one catalog filename inside the VPS-managed plant image folder."""
    name = Path(str(raw_name or "")).name.strip()
    if not name:
        return None
    path = PLANT_IMAGE_DIR / name
    return str(path) if path.is_file() else None


def _catalog_photos(plant: Plant) -> tuple[str | None, str | None]:
    """Return seed and microgreen images independently when both are available."""
    seed_photo = _catalog_image(getattr(plant, "seed_image_name", ""))
    microgreen_photo = _catalog_image(getattr(plant, "microgreen_image_name", ""))
    return seed_photo, microgreen_photo


async def _rental_slot(slot_id: int):
    slots = await core.list_available_slots(50)
    return next((item for item in slots if item.id == slot_id), None)


async def _plant_by_id(plant_id: str) -> Plant | None:
    async with SessionLocal() as session:
        return await session.get(Plant, plant_id)


async def _latest_real_photo(plant_id: str) -> str | None:
    """Return the latest public manually-published photo for this plant species."""
    async with SessionLocal() as session:
        photo = (
            await session.execute(
                select(PlantingPhoto)
                .join(Planting, Planting.id == PlantingPhoto.planting_id)
                .where(
                    Planting.plant_id == plant_id,
                    PlantingPhoto.is_public.is_(True),
                )
                .order_by(PlantingPhoto.captured_at.desc(), PlantingPhoto.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if photo is None:
        return None
    path = Path(photo.file_path)
    return str(path) if path.is_file() else None


async def show_rental_plants(bot, chat_id: int, tg: dict, slot_id: int) -> None:
    """Offer one clean full-width button per plant; details precede final selection."""
    lang = core.language_for(tg)
    slot = await _rental_slot(slot_id)
    if slot is None:
        await show_rental_slots(bot, chat_id, tg)
        return

    plants = await list_rentable_plants(50)
    plants.sort(
        key=lambda plant: (
            core.plant_name(plant, lang).casefold(),
            (getattr(plant, "code", "") or "").casefold(),
        )
    )
    if not plants:
        await bot.send_message(
            chat_id,
            seed_text(lang),
            reply_markup={
                "inline_keyboard": [[
                    {"text": core.st(lang, "back_garden"), "callback_data": "menu:garden"}
                ]]
            },
        )
        return

    rows = []
    for plant in plants:
        name = core.plant_name(plant, lang)
        days = max(1, int(plant.grow_days or 1))
        price = int(plant.rental_price_kisa or 0)
        rows.append([{
            "text": f"🌱 {name} · {days}{info_text(lang, 'days_short')} · Ⓚ{price} · ℹ️"[:60],
            "callback_data": f"rent:info:{slot_id}:{plant.id}",
        }])
    rows.append([{"text": core.st(lang, "cancel"), "callback_data": "menu:garden"}])
    await bot.send_message(
        chat_id,
        core.st(lang, "rent_choose_plant", rack=slot.rack_id, slot=slot.slot_number),
        reply_markup={"inline_keyboard": rows},
    )


async def show_rental_plant_info(
    bot,
    chat_id: int,
    tg: dict,
    slot_id: int,
    plant_id: str,
) -> None:
    lang = core.language_for(tg)
    slot = await _rental_slot(slot_id)
    if slot is None:
        await show_rental_slots(bot, chat_id, tg)
        return

    plant = await _plant_by_id(plant_id)
    if plant is None or not plant.active:
        await show_rental_plants(bot, chat_id, tg, slot_id)
        return

    # Do not let the info card turn an unavailable plant into a selectable one.
    rentable = {item.id for item in await list_rentable_plants(100)}
    if plant.id not in rentable:
        await show_rental_plants(bot, chat_id, tg, slot_id)
        return

    name = core.plant_name(plant, lang)
    description = plant_description(plant, lang).strip()
    days = max(1, int(plant.grow_days or 1))
    price = int(plant.rental_price_kisa or 0)

    seed_photo, microgreen_photo = _catalog_photos(plant)
    real_photo = None
    if not seed_photo and not microgreen_photo:
        real_photo = await _latest_real_photo(plant.id)

    caption = (
        f"🌱 <b>{escape(name)}</b>\n\n"
        f"⏱ <b>{escape(info_text(lang, 'grow_days'))}:</b> {days} {escape(info_text(lang, 'days'))}\n"
        f"🪙 <b>{escape(info_text(lang, 'price'))}:</b> Ⓚ {price}\n\n"
        f"<b>{escape(info_text(lang, 'description'))}</b>\n"
        f"{escape(description or info_text(lang, 'description_empty'))}"
    )
    keyboard = {
        "inline_keyboard": [
            [{
                "text": info_text(lang, "choose")[:60],
                "callback_data": f"rent:plant:{slot_id}:{plant.id}",
            }],
            [{
                "text": info_text(lang, "back")[:60],
                "callback_data": f"rent:list:{slot_id}",
            }],
        ]
    }

    # If both catalog photos exist, show the seed photo first and the finished
    # microgreen photo second. The second message carries the full card/actions.
    if seed_photo and microgreen_photo:
        try:
            await bot.send_photo(
                chat_id,
                seed_photo,
                caption=(
                    f"🌾 <b>{escape(info_text(lang, 'seed_photo'))}</b>\n"
                    f"{escape(name)}"
                ),
            )
        except Exception:
            core.logger.exception("Could not send rental seed photo %s", seed_photo)

        try:
            await bot.send_photo(
                chat_id,
                microgreen_photo,
                caption=(
                    caption
                    + f"\n\n📷 <i>{escape(info_text(lang, 'microgreen_photo'))}</i>"
                )[:1024],
                reply_markup=keyboard,
            )
            return
        except Exception:
            core.logger.exception(
                "Could not send rental microgreen photo %s", microgreen_photo
            )

    # If only one catalog photo exists, attach the complete card to that photo.
    single_photo = microgreen_photo or seed_photo or real_photo
    if single_photo:
        if microgreen_photo:
            photo_label = info_text(lang, "microgreen_photo")
        elif seed_photo:
            photo_label = info_text(lang, "seed_photo")
        else:
            photo_label = info_text(lang, "real_photo")
        try:
            await bot.send_photo(
                chat_id,
                single_photo,
                caption=(caption + f"\n\n📷 <i>{escape(photo_label)}</i>")[:1024],
                reply_markup=keyboard,
            )
            return
        except Exception:
            core.logger.exception("Could not send rental plant detail photo %s", single_photo)

    await bot.send_message(
        chat_id,
        caption + f"\n\n<i>{escape(info_text(lang, 'no_photo'))}</i>",
        reply_markup=keyboard,
    )


async def show_rental_slots(bot, chat_id: int, tg: dict) -> None:
    """Use the existing first-free-container flow, but stop early if seeds are unavailable."""
    lang = core.language_for(tg)
    plants = await list_rentable_plants(1)
    if not plants:
        await bot.send_message(
            chat_id,
            seed_text(lang),
            reply_markup={
                "inline_keyboard": [[
                    {"text": core.st(lang, "back_garden"), "callback_data": "menu:garden"}
                ]]
            },
        )
        return

    slots = await core.list_available_slots(1)
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


async def handle_callback(bot, query: dict) -> None:
    data = str(query.get("data") or "")
    if not (data.startswith("rent:info:") or data.startswith("rent:list:")):
        await _original_handle_callback(bot, query)
        return

    qid = query.get("id")
    tg = query.get("from")
    chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
    if not qid or tg is None or chat_id is None:
        return

    await bot.answer_callback_query(qid)

    if data.startswith("rent:list:"):
        try:
            slot_id = int(data.rsplit(":", 1)[1])
        except ValueError:
            return
        await show_rental_plants(bot, chat_id, tg, slot_id)
        return

    parts = data.split(":", 3)
    if len(parts) != 4:
        return
    try:
        slot_id = int(parts[2])
    except ValueError:
        return
    await show_rental_plant_info(bot, chat_id, tg, slot_id, parts[3])


# worker.py and worker_core resolve these functions through core globals at
# runtime. Keep all photo, watering and lifecycle wrappers, replacing only the
# rental inventory source and rental picker.
core.list_active_plants = list_rentable_plants
core.show_rental_plants = show_rental_plants
core.show_rental_slots = show_rental_slots
core.handle_callback = handle_callback


if __name__ == "__main__":
    asyncio.run(core.run())
