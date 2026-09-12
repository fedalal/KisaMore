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
        "more": "ℹ️ Details",
        "title": "Plant details",
        "grow_days": "Growing time",
        "days": "days",
        "price": "Rental price",
        "description": "About this plant",
        "description_empty": "No additional description is available yet.",
        "catalog_microgreen": "The image above shows this plant as microgreens.",
        "catalog_seed": "The image above shows the seeds for this plant.",
        "real_photo": "A recent real greenhouse photo of this plant is shown above.",
        "no_photo": "A photo of this plant is not available yet.",
        "choose": "✅ Choose this plant",
        "back": "⬅️ Back to plants",
    },
    "ru": {
        "days_short": "дн",
        "more": "ℹ️ Подробнее",
        "title": "О растении",
        "grow_days": "Срок выращивания",
        "days": "дней",
        "price": "Стоимость аренды",
        "description": "Описание",
        "description_empty": "Дополнительное описание пока не заполнено.",
        "catalog_microgreen": "Выше показано, как выглядит готовая микрозелень этого растения.",
        "catalog_seed": "Выше показаны семена этого растения.",
        "real_photo": "Выше показана свежая реальная фотография этого растения из теплицы.",
        "no_photo": "Фотография этого растения пока не загружена.",
        "choose": "✅ Выбрать это растение",
        "back": "⬅️ К списку растений",
    },
    "de": {
        "days_short": "T",
        "more": "ℹ️ Details",
        "title": "Pflanzeninfo",
        "grow_days": "Anbauzeit",
        "days": "Tage",
        "price": "Mietpreis",
        "description": "Beschreibung",
        "description_empty": "Noch keine zusätzliche Beschreibung verfügbar.",
        "catalog_microgreen": "Das Bild oben zeigt diese Pflanze als Microgreens.",
        "catalog_seed": "Das Bild oben zeigt das Saatgut dieser Pflanze.",
        "real_photo": "Oben sehen Sie ein aktuelles echtes Foto dieser Pflanze aus dem Gewächshaus.",
        "no_photo": "Für diese Pflanze ist noch kein Foto verfügbar.",
        "choose": "✅ Diese Pflanze wählen",
        "back": "⬅️ Zur Pflanzenliste",
    },
    "fr": {
        "days_short": "j",
        "more": "ℹ️ Détails",
        "title": "Détails de la plante",
        "grow_days": "Durée de culture",
        "days": "jours",
        "price": "Prix de location",
        "description": "Description",
        "description_empty": "Aucune description supplémentaire pour le moment.",
        "catalog_microgreen": "L’image ci-dessus montre cette plante sous forme de micropousses.",
        "catalog_seed": "L’image ci-dessus montre les graines de cette plante.",
        "real_photo": "Une photo récente et réelle de cette plante dans la serre est affichée ci-dessus.",
        "no_photo": "Aucune photo de cette plante n’est encore disponible.",
        "choose": "✅ Choisir cette plante",
        "back": "⬅️ Retour aux plantes",
    },
    "es": {
        "days_short": "d",
        "more": "ℹ️ Detalles",
        "title": "Detalles de la planta",
        "grow_days": "Tiempo de cultivo",
        "days": "días",
        "price": "Precio del alquiler",
        "description": "Descripción",
        "description_empty": "Todavía no hay una descripción adicional.",
        "catalog_microgreen": "La imagen de arriba muestra esta planta como microbrotes.",
        "catalog_seed": "La imagen de arriba muestra las semillas de esta planta.",
        "real_photo": "Arriba se muestra una foto real y reciente de esta planta en el invernadero.",
        "no_photo": "Todavía no hay una foto disponible de esta planta.",
        "choose": "✅ Elegir esta planta",
        "back": "⬅️ Volver a las plantas",
    },
    "it": {
        "days_short": "g",
        "more": "ℹ️ Dettagli",
        "title": "Dettagli della pianta",
        "grow_days": "Tempo di coltivazione",
        "days": "giorni",
        "price": "Prezzo del noleggio",
        "description": "Descrizione",
        "description_empty": "Non è ancora disponibile una descrizione aggiuntiva.",
        "catalog_microgreen": "L’immagine sopra mostra questa pianta come microgreens.",
        "catalog_seed": "L’immagine sopra mostra i semi di questa pianta.",
        "real_photo": "Sopra è mostrata una foto reale e recente di questa pianta nella serra.",
        "no_photo": "Non è ancora disponibile una foto di questa pianta.",
        "choose": "✅ Scegli questa pianta",
        "back": "⬅️ Torna alle piante",
    },
    "pt": {
        "days_short": "d",
        "more": "ℹ️ Detalhes",
        "title": "Detalhes da planta",
        "grow_days": "Tempo de cultivo",
        "days": "dias",
        "price": "Preço do aluguel",
        "description": "Descrição",
        "description_empty": "Ainda não há uma descrição adicional.",
        "catalog_microgreen": "A imagem acima mostra esta planta como microverdes.",
        "catalog_seed": "A imagem acima mostra as sementes desta planta.",
        "real_photo": "Acima está uma foto real e recente desta planta na estufa.",
        "no_photo": "Ainda não há uma foto disponível desta planta.",
        "choose": "✅ Escolher esta planta",
        "back": "⬅️ Voltar às plantas",
    },
    "pl": {
        "days_short": "d",
        "more": "ℹ️ Szczegóły",
        "title": "Informacje o roślinie",
        "grow_days": "Czas uprawy",
        "days": "dni",
        "price": "Cena wynajmu",
        "description": "Opis",
        "description_empty": "Dodatkowy opis nie jest jeszcze dostępny.",
        "catalog_microgreen": "Powyżej pokazano tę roślinę jako mikrozieleninę.",
        "catalog_seed": "Powyżej pokazano nasiona tej rośliny.",
        "real_photo": "Powyżej pokazano aktualne, prawdziwe zdjęcie tej rośliny ze szklarni.",
        "no_photo": "Zdjęcie tej rośliny nie jest jeszcze dostępne.",
        "choose": "✅ Wybierz tę roślinę",
        "back": "⬅️ Wróć do roślin",
    },
    "zh": {
        "days_short": "天",
        "more": "ℹ️ 详情",
        "title": "植物详情",
        "grow_days": "生长周期",
        "days": "天",
        "price": "租用价格",
        "description": "介绍",
        "description_empty": "暂时没有更多介绍。",
        "catalog_microgreen": "上图显示的是这种植物长成微型蔬菜后的样子。",
        "catalog_seed": "上图显示的是这种植物的种子。",
        "real_photo": "上方显示的是这株植物在温室中的近期实拍照片。",
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


def _catalog_photo(plant: Plant) -> tuple[str | None, str | None]:
    """Resolve catalog image filenames against the VPS-managed image folder.

    The filename values come from the plant catalog synchronized from Raspberry
    Pi. Only the basename is used so a catalog value can never escape the
    dedicated image directory.
    """
    candidates = (
        (getattr(plant, "microgreen_image_name", ""), "catalog_microgreen"),
        (getattr(plant, "seed_image_name", ""), "catalog_seed"),
    )
    for raw_name, note_key in candidates:
        name = Path(str(raw_name or "")).name.strip()
        if not name:
            continue
        path = PLANT_IMAGE_DIR / name
        if path.is_file():
            return str(path), note_key
    return None, None


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
    """Offer rentable plants with growing time, price and a separate details action."""
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
        rows.append([
            {
                "text": f"🌱 {name} · {days}{info_text(lang, 'days_short')} · Ⓚ{price}"[:54],
                "callback_data": f"rent:plant:{slot_id}:{plant.id}",
            },
            {
                "text": "ℹ️",
                "callback_data": f"rent:info:{slot_id}:{plant.id}",
            },
        ])
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

    catalog_photo, catalog_note_key = _catalog_photo(plant)
    real_photo = None if catalog_photo else await _latest_real_photo(plant.id)
    photo_path = catalog_photo or real_photo
    if catalog_photo and catalog_note_key:
        photo_note = info_text(lang, catalog_note_key)
    elif real_photo:
        photo_note = info_text(lang, "real_photo")
    else:
        photo_note = info_text(lang, "no_photo")

    caption = (
        f"🌱 <b>{escape(name)}</b>\n\n"
        f"⏱ <b>{escape(info_text(lang, 'grow_days'))}:</b> {days} {escape(info_text(lang, 'days'))}\n"
        f"🪙 <b>{escape(info_text(lang, 'price'))}:</b> Ⓚ {price}\n\n"
        f"<b>{escape(info_text(lang, 'description'))}</b>\n"
        f"{escape(description or info_text(lang, 'description_empty'))}\n\n"
        f"<i>{escape(photo_note)}</i>"
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

    if photo_path:
        try:
            await bot.send_photo(chat_id, photo_path, caption=caption[:1024], reply_markup=keyboard)
            return
        except Exception:
            core.logger.exception("Could not send rental plant detail photo %s", photo_path)

    await bot.send_message(chat_id, caption, reply_markup=keyboard)


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
