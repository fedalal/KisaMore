from __future__ import annotations

import asyncio
from html import escape

from sqlalchemy import select

from ..db import SessionLocal
from ..models import Plant, Planting, RackSlot
from . import worker_slot_photos as media
from .watering_service import (
    ExtraWateringInsufficientBalance,
    ExtraWateringTooClose,
    WateringUnavailable,
    buy_extra_watering,
    get_watering_context,
    set_watering_adjustment,
)


core = media.core
_original_handle_callback = core.handle_callback


WATER_TEXT = {
    "en": {
        "button": "💧 Watering",
        "title": "💧 <b>Watering</b>",
        "schedule": "Daily schedule",
        "no_schedule": "No scheduled watering is configured yet.",
        "adjustment": "Your adjustment: {value}%",
        "interval": "Minimum interval between waterings: {minutes} min.",
        "extra": "Extra watering",
        "not_started": "Extra watering becomes available after the planting has started.",
        "adjusted": "Watering amount changed to {value}%.",
        "ordered": "✅ Extra watering: {ml} ml. Charged Ⓚ {price}. Balance: Ⓚ {balance}. The administrator has received the task.",
        "too_close": "Extra watering is unavailable because another watering is too close. Minimum interval: {minutes} min.",
        "insufficient": "Not enough Kisa. Price: Ⓚ {price}. Balance: Ⓚ {balance}.",
        "unavailable": "Watering settings are not available for this rental yet.",
        "standard": "Standard",
    },
    "ru": {
        "button": "💧 Полив",
        "title": "💧 <b>Полив</b>",
        "schedule": "Ежедневное расписание",
        "no_schedule": "Плановый полив для этого растения пока не настроен.",
        "adjustment": "Ваша коррекция объёма: {value}%",
        "interval": "Минимальный интервал между поливами: {minutes} мин.",
        "extra": "Дополнительный полив",
        "not_started": "Дополнительный полив станет доступен после начала выращивания.",
        "adjusted": "Объём планового полива изменён на {value}%.",
        "ordered": "✅ Дополнительный полив {ml} мл заказан. Списано Ⓚ {price}. Баланс: Ⓚ {balance}. Задание уже появилось у администратора.",
        "too_close": "Дополнительный полив сейчас нельзя заказать: рядом другой полив. Минимальный интервал — {minutes} мин.",
        "insufficient": "Недостаточно Kisa. Цена: Ⓚ {price}. Баланс: Ⓚ {balance}.",
        "unavailable": "Настройки полива для этой аренды пока недоступны.",
        "standard": "Стандарт",
    },
    "de": {"button":"💧 Bewässerung","title":"💧 <b>Bewässerung</b>","schedule":"Täglicher Plan","no_schedule":"Noch kein Bewässerungsplan.","adjustment":"Ihre Anpassung: {value}%","interval":"Mindestabstand: {minutes} Min.","extra":"Zusätzliche Bewässerung","not_started":"Zusätzliche Bewässerung ist nach Pflanzbeginn verfügbar.","adjusted":"Bewässerungsmenge auf {value}% geändert.","ordered":"✅ Zusätzliche Bewässerung {ml} ml bestellt. Ⓚ {price} abgezogen. Guthaben: Ⓚ {balance}.","too_close":"Zu nah an einer anderen Bewässerung. Mindestabstand: {minutes} Min.","insufficient":"Nicht genug Kisa. Preis: Ⓚ {price}. Guthaben: Ⓚ {balance}.","unavailable":"Bewässerungseinstellungen sind noch nicht verfügbar.","standard":"Standard"},
    "fr": {"button":"💧 Arrosage","title":"💧 <b>Arrosage</b>","schedule":"Programme quotidien","no_schedule":"Aucun arrosage planifié.","adjustment":"Votre réglage : {value}%","interval":"Intervalle minimum : {minutes} min.","extra":"Arrosage supplémentaire","not_started":"Disponible après le début de la culture.","adjusted":"Volume d’arrosage réglé à {value}%.","ordered":"✅ Arrosage supplémentaire de {ml} ml commandé. Ⓚ {price} débités. Solde : Ⓚ {balance}.","too_close":"Un autre arrosage est trop proche. Intervalle minimum : {minutes} min.","insufficient":"Kisa insuffisants. Prix : Ⓚ {price}. Solde : Ⓚ {balance}.","unavailable":"Réglages d’arrosage indisponibles pour le moment.","standard":"Standard"},
    "es": {"button":"💧 Riego","title":"💧 <b>Riego</b>","schedule":"Horario diario","no_schedule":"No hay riego programado.","adjustment":"Tu ajuste: {value}%","interval":"Intervalo mínimo: {minutes} min.","extra":"Riego adicional","not_started":"Disponible después de iniciar el cultivo.","adjusted":"Volumen de riego cambiado a {value}%.","ordered":"✅ Riego adicional de {ml} ml solicitado. Se descontaron Ⓚ {price}. Saldo: Ⓚ {balance}.","too_close":"Hay otro riego demasiado cerca. Intervalo mínimo: {minutes} min.","insufficient":"Kisa insuficientes. Precio: Ⓚ {price}. Saldo: Ⓚ {balance}.","unavailable":"Los ajustes de riego aún no están disponibles.","standard":"Estándar"},
    "it": {"button":"💧 Irrigazione","title":"💧 <b>Irrigazione</b>","schedule":"Programma giornaliero","no_schedule":"Nessuna irrigazione programmata.","adjustment":"La tua regolazione: {value}%","interval":"Intervallo minimo: {minutes} min.","extra":"Irrigazione extra","not_started":"Disponibile dopo l’inizio della coltivazione.","adjusted":"Volume irrigazione impostato a {value}%.","ordered":"✅ Irrigazione extra {ml} ml ordinata. Addebitati Ⓚ {price}. Saldo: Ⓚ {balance}.","too_close":"Un’altra irrigazione è troppo vicina. Intervallo minimo: {minutes} min.","insufficient":"Kisa insufficienti. Prezzo: Ⓚ {price}. Saldo: Ⓚ {balance}.","unavailable":"Impostazioni irrigazione non ancora disponibili.","standard":"Standard"},
    "pt": {"button":"💧 Rega","title":"💧 <b>Rega</b>","schedule":"Agenda diária","no_schedule":"Nenhuma rega programada.","adjustment":"Seu ajuste: {value}%","interval":"Intervalo mínimo: {minutes} min.","extra":"Rega extra","not_started":"Disponível após o início do cultivo.","adjusted":"Volume de rega alterado para {value}%.","ordered":"✅ Rega extra de {ml} ml pedida. Ⓚ {price} debitados. Saldo: Ⓚ {balance}.","too_close":"Outra rega está muito próxima. Intervalo mínimo: {minutes} min.","insufficient":"Kisa insuficientes. Preço: Ⓚ {price}. Saldo: Ⓚ {balance}.","unavailable":"Configurações de rega ainda indisponíveis.","standard":"Padrão"},
    "pl": {"button":"💧 Podlewanie","title":"💧 <b>Podlewanie</b>","schedule":"Plan dzienny","no_schedule":"Brak zaplanowanego podlewania.","adjustment":"Twoja korekta: {value}%","interval":"Minimalny odstęp: {minutes} min.","extra":"Dodatkowe podlewanie","not_started":"Dostępne po rozpoczęciu uprawy.","adjusted":"Ilość wody zmieniona na {value}%.","ordered":"✅ Zamówiono dodatkowe {ml} ml. Pobrano Ⓚ {price}. Saldo: Ⓚ {balance}.","too_close":"Inne podlewanie jest zbyt blisko. Minimalny odstęp: {minutes} min.","insufficient":"Za mało Kisa. Cena: Ⓚ {price}. Saldo: Ⓚ {balance}.","unavailable":"Ustawienia podlewania nie są jeszcze dostępne.","standard":"Standard"},
    "zh": {"button":"💧 浇水","title":"💧 <b>浇水</b>","schedule":"每日计划","no_schedule":"尚未设置计划浇水。","adjustment":"您的调整：{value}%","interval":"最小间隔：{minutes} 分钟。","extra":"额外浇水","not_started":"种植开始后可购买额外浇水。","adjusted":"浇水量已调整为 {value}%。","ordered":"✅ 已订购额外 {ml} 毫升浇水。扣除 Ⓚ {price}。余额：Ⓚ {balance}。","too_close":"与其他浇水时间太接近。最小间隔：{minutes} 分钟。","insufficient":"Kisa 不足。价格：Ⓚ {price}。余额：Ⓚ {balance}。","unavailable":"此租用的浇水设置暂不可用。","standard":"标准"},
}


def wt(lang: str, key: str, **kwargs) -> str:
    values = WATER_TEXT.get(lang) or WATER_TEXT["en"]
    return (values.get(key) or WATER_TEXT["en"][key]).format(**kwargs)


async def show_garden(bot, chat_id: int, tg: dict) -> None:
    lang = core.language_for(tg)
    user, _ = await core.get_or_create_user(tg)
    followed = await core.list_followed_plantings(user.id, 6)
    requests = [
        row for row in await core.rental_requests(user.id, 20)
        if row[0].status in ("requested", "approved")
    ][:6]
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
        device_ids = {item.device_id for item in allocations if item.device_id}
        plants_by_id = {}
        planting_by_position = {}
        async with SessionLocal() as session:
            if plant_ids:
                plant_rows = (
                    await session.execute(select(Plant).where(Plant.id.in_(plant_ids)))
                ).scalars().all()
                plants_by_id = {item.id: item for item in plant_rows}
            if device_ids:
                planting_rows = (
                    await session.execute(
                        select(Planting, RackSlot)
                        .join(RackSlot, RackSlot.id == Planting.slot_id)
                        .where(
                            RackSlot.device_id.in_(device_ids),
                            Planting.status.in_(("planned", "growing", "ready")),
                        )
                    )
                ).all()
                planting_by_position = {
                    (slot.device_id, slot.rack_id, slot.slot_number): planting
                    for planting, slot in planting_rows
                }

        parts.append("\n" + media.existing.rt(lang, "active"))
        for allocation in allocations:
            plant = plants_by_id.get(allocation.plant_id)
            name = core.plant_name(plant, lang) if plant else "🌱"
            parts.append(
                media.existing.rt(
                    lang,
                    "allocation",
                    plant=escape(name),
                    rack=allocation.rack_id,
                    slot=allocation.slot_number or "—",
                )
            )
            if allocation.slot_number:
                planting = planting_by_position.get(
                    (allocation.device_id, allocation.rack_id, allocation.slot_number)
                )
                if planting is not None:
                    buttons.append([{
                        "text": f"📷 {name} · {allocation.rack_id}/{allocation.slot_number}"[:60],
                        "callback_data": f"plant:show:{planting.id}:0",
                    }])
                buttons.append([{
                    "text": f"{wt(lang, 'button')} · {allocation.rack_id}/{allocation.slot_number}"[:60],
                    "callback_data": f"water:menu:{allocation.id}",
                }])

    if not followed and not requests and not allocations:
        parts.append("\n" + core.st(lang, "garden_empty"))
    buttons.append([{"text": core.st(lang, "rent_button"), "callback_data": "rent:start"}])
    buttons.append([{"text": core.t(lang, "back_home"), "callback_data": "menu:home"}])
    await bot.send_message(chat_id, "\n".join(parts), reply_markup={"inline_keyboard": buttons})


async def show_watering_menu(bot, chat_id: int, tg: dict, allocation_id: str) -> None:
    lang = core.language_for(tg)
    user, _ = await core.get_or_create_user(tg)
    try:
        context = await get_watering_context(user.id, allocation_id)
    except WateringUnavailable:
        await bot.send_message(chat_id, wt(lang, "unavailable"))
        return

    name = core.plant_name(context.plant, lang)
    parts = [
        wt(lang, "title"),
        f"🌱 {escape(name)} · {context.rack_id}/{context.slot_number}",
        "",
        f"<b>{wt(lang, 'schedule')}</b>",
    ]
    if context.schedule:
        for item in context.schedule:
            parts.append(f"• {escape(item['time'])} — <b>{item['ml']} ml</b>")
    else:
        parts.append(wt(lang, "no_schedule"))

    signed = f"+{context.adjustment_percent}" if context.adjustment_percent > 0 else str(context.adjustment_percent)
    parts.append("")
    parts.append(wt(lang, "adjustment", value=signed))
    parts.append(wt(lang, "interval", minutes=context.min_interval_minutes))

    buttons = []
    adjustment_buttons = []
    for value in context.allowed_adjustments:
        label = wt(lang, "standard") if value == 0 else f"{value:+d}%"
        if value == context.adjustment_percent:
            label = f"✓ {label}"
        adjustment_buttons.append({
            "text": label,
            "callback_data": f"water:adjust:{value}:{allocation_id}",
        })
    for index in range(0, len(adjustment_buttons), 3):
        buttons.append(adjustment_buttons[index:index + 3])

    parts.append("")
    parts.append(f"<b>{wt(lang, 'extra')}</b>")
    if context.planting is None:
        parts.append(wt(lang, "not_started"))
    elif context.extra_options:
        for option in context.extra_options:
            buttons.append([{
                "text": f"💧 +{option['ml']} ml · Ⓚ {option['price_kisa']}",
                "callback_data": f"water:extra:{option['ml']}:{allocation_id}",
            }])
    else:
        parts.append("—")

    buttons.append([{"text": core.st(lang, "back_garden"), "callback_data": "menu:garden"}])
    await bot.send_message(chat_id, "\n".join(parts), reply_markup={"inline_keyboard": buttons})


async def handle_callback(bot, query: dict) -> None:
    data = str(query.get("data") or "")
    if not data.startswith("water:"):
        await _original_handle_callback(bot, query)
        return

    qid = query.get("id")
    tg = query.get("from")
    chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
    if not qid or tg is None or chat_id is None:
        return
    lang = core.language_for(tg)
    user, _ = await core.get_or_create_user(tg)
    await bot.answer_callback_query(qid)

    parts = data.split(":")
    if len(parts) == 3 and parts[1] == "menu":
        await show_watering_menu(bot, chat_id, tg, parts[2])
        return

    if len(parts) == 4 and parts[1] == "adjust":
        try:
            value = int(parts[2])
            context = await set_watering_adjustment(user.id, parts[3], value)
        except (ValueError, WateringUnavailable):
            await bot.send_message(chat_id, wt(lang, "unavailable"))
            return
        signed = f"+{context.adjustment_percent}" if context.adjustment_percent > 0 else str(context.adjustment_percent)
        await bot.send_message(chat_id, wt(lang, "adjusted", value=signed))
        await show_watering_menu(bot, chat_id, tg, parts[3])
        return

    if len(parts) == 4 and parts[1] == "extra":
        try:
            ml = int(parts[2])
            context, _, balance, price = await buy_extra_watering(user.id, parts[3], ml)
        except ExtraWateringTooClose:
            try:
                context = await get_watering_context(user.id, parts[3])
                minutes = context.min_interval_minutes
            except Exception:
                minutes = 240
            await bot.send_message(chat_id, wt(lang, "too_close", minutes=minutes))
            return
        except ExtraWateringInsufficientBalance as exc:
            await bot.send_message(chat_id, wt(lang, "insufficient", price=exc.price, balance=exc.balance))
            return
        except (ValueError, WateringUnavailable):
            await bot.send_message(chat_id, wt(lang, "unavailable"))
            return
        await bot.send_message(
            chat_id,
            wt(lang, "ordered", ml=ml, price=price, balance=balance),
            reply_markup={"inline_keyboard": [[{"text": core.st(lang, "back_garden"), "callback_data": "menu:garden"}]]},
        )
        return


core.show_garden = show_garden
core.handle_callback = handle_callback


if __name__ == "__main__":
    asyncio.run(core.run())
