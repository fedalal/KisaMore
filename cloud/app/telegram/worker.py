from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from html import escape
import logging
import secrets

from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal, create_tables, engine
from .bot import TelegramBotAPI
from .i18n import language_for, t
from .models import StarPayment, TelegramUser, WalletTransaction
from .service import (
    add_comment,
    clear_state,
    community_top,
    create_rental_request,
    day_number,
    get_or_create_user,
    get_plant_card,
    get_state,
    linked_allocations,
    list_active_plants,
    list_available_slots,
    list_comments,
    list_followed_plantings,
    list_plantings,
    localized_value,
    mark_follow_notified,
    pending_follow_notifications,
    profile_stats,
    rental_requests,
    resolve_photo_path,
    send_gift,
    set_state,
    toggle_follow,
    toggle_vote,
    wallet_for_update,
    wallet_history,
)
from .social_i18n import st


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()
PACKAGES = {10: 100, 50: 550, 100: 1200, 250: 3250}


def main_keyboard(lang: str) -> dict:
    return {"inline_keyboard": [
        [{"text": t(lang, "menu_plants"), "callback_data": "menu:plants"}, {"text": t(lang, "menu_garden"), "callback_data": "menu:garden"}],
        [{"text": t(lang, "menu_community"), "callback_data": "menu:community"}, {"text": t(lang, "menu_wallet"), "callback_data": "menu:wallet"}],
        [{"text": t(lang, "menu_profile"), "callback_data": "menu:profile"}],
    ]}


def back_keyboard(lang: str) -> dict:
    return {"inline_keyboard": [[{"text": t(lang, "back_home"), "callback_data": "menu:home"}]]}


def terms_keyboard(lang: str, *, wallet_back: bool = True) -> dict:
    rows = [[{"text": t(lang, "accept"), "callback_data": "terms:accept"}]]
    if wallet_back:
        rows.append([{"text": t(lang, "back"), "callback_data": "menu:wallet"}])
    return {"inline_keyboard": rows}


def invoice_payload(tg_id: int, stars: int, kisa: int) -> str:
    return f"kisa:{tg_id}:{stars}:{kisa}:{secrets.token_hex(6)}"


def parse_payload(payload: str):
    parts = payload.split(":")
    if len(parts) != 5 or parts[0] != "kisa":
        return None
    try:
        return int(parts[1]), int(parts[2]), int(parts[3])
    except ValueError:
        return None


def plant_name(plant, lang: str) -> str:
    return localized_value(getattr(plant, "names", None), lang, getattr(plant, "code", "Plant"))


def status_text(lang: str, status: str) -> str:
    return st(lang, f"status_{status}")


def plant_keyboard(lang: str, card, index: int, total: int) -> dict:
    vote_like = "✅❤️" if card.my_vote == "like" else st(lang, "like")
    vote_dislike = "✅👎" if card.my_vote == "dislike" else st(lang, "dislike")
    follow = st(lang, "unfollow") if card.following else st(lang, "follow")
    rows = [
        [{"text": vote_like, "callback_data": f"vote:like:{card.planting.id}:{index}"}, {"text": vote_dislike, "callback_data": f"vote:dislike:{card.planting.id}:{index}"}],
        [{"text": st(lang, "write_comment"), "callback_data": f"comment:write:{card.planting.id}"}, {"text": st(lang, "view_comments", count=card.comments), "callback_data": f"comment:list:{card.planting.id}:{index}"}],
        [{"text": follow, "callback_data": f"follow:{card.planting.id}:{index}"}, {"text": st(lang, "gift"), "callback_data": f"gift:menu:{card.planting.id}:{index}"}],
        [{"text": st(lang, "timelapse"), "callback_data": f"timelapse:{card.planting.id}"}],
    ]
    nav = []
    if index > 0:
        nav.append({"text": st(lang, "previous"), "callback_data": f"feed:{index - 1}"})
    if index + 1 < total:
        nav.append({"text": st(lang, "next"), "callback_data": f"feed:{index + 1}"})
    if nav:
        rows.append(nav)
    rows.append([{"text": t(lang, "back_home"), "callback_data": "menu:home"}])
    return {"inline_keyboard": rows}


async def show_home(bot: TelegramBotAPI, chat_id: int, tg: dict) -> None:
    lang = language_for(tg)
    user, wallet = await get_or_create_user(tg)
    await bot.send_message(chat_id, t(lang, "home", name=escape(user.first_name or "KisaMore"), balance=wallet.balance), reply_markup=main_keyboard(lang))


async def show_wallet(bot: TelegramBotAPI, chat_id: int, tg: dict) -> None:
    lang = language_for(tg)
    user, wallet = await get_or_create_user(tg)
    rows = []
    if user.terms_accepted_at:
        for stars, kisa in PACKAGES.items():
            rows.append([{"text": f"⭐ {stars} → 🪙 {kisa} Kisa", "callback_data": f"wallet:buy:{stars}"}])
        note = t(lang, "wallet_choose")
    else:
        rows.append([{"text": t(lang, "read_terms"), "callback_data": "terms:show"}])
        note = t(lang, "wallet_terms_required")
    history = await wallet_history(user.id, 6)
    extra = st(lang, "wallet_history_title") if history else st(lang, "wallet_history_empty")
    for item in history:
        key = "wallet_tx_plus" if item.amount >= 0 else "wallet_tx_minus"
        extra += "\n" + st(lang, key, amount=item.amount, kind=escape(item.kind))
    rows.append([{"text": t(lang, "back_home"), "callback_data": "menu:home"}])
    await bot.send_message(chat_id, f"{t(lang, 'wallet_title')}\n\n{t(lang, 'balance', balance=wallet.balance)}\n\n{note}{extra}", reply_markup={"inline_keyboard": rows})


async def show_profile(bot: TelegramBotAPI, chat_id: int, tg: dict) -> None:
    lang = language_for(tg)
    user, wallet = await get_or_create_user(tg)
    username = f"@{escape(user.username)}" if user.username else "—"
    stats = await profile_stats(user.id)
    text = t(lang, "profile", name=escape(user.first_name or "—"), username=username, balance=wallet.balance)
    text += st(lang, "profile_stats", likes=stats["likes"], comments=stats["comments"], follows=stats["follows"], gifts=stats["gifts"], spent=stats["kisa_spent"])
    await bot.send_message(chat_id, text, reply_markup=back_keyboard(lang))


async def show_plant_at(bot: TelegramBotAPI, chat_id: int, tg: dict, index: int = 0) -> None:
    lang = language_for(tg)
    user, _ = await get_or_create_user(tg)
    rows = await list_plantings(limit=20)
    if not rows:
        await bot.send_message(chat_id, st(lang, "no_plants"), reply_markup=back_keyboard(lang))
        return
    index = max(0, min(index, len(rows) - 1))
    planting, _, _ = rows[index]
    await show_plant_card(bot, chat_id, tg, planting.id, index=index, total=len(rows), user_id=user.id)


async def show_plant_card(bot: TelegramBotAPI, chat_id: int, tg: dict, planting_id: str, *, index: int = 0, total: int | None = None, user_id: int | None = None) -> None:
    lang = language_for(tg)
    if user_id is None:
        user, _ = await get_or_create_user(tg)
        user_id = user.id
    card = await get_plant_card(planting_id, user_id)
    if card is None:
        await show_plant_at(bot, chat_id, tg, 0)
        return
    if total is None:
        total = max(1, len(await list_plantings(limit=20)))
    sensor = ""
    if card.rack and (card.rack.soil_temperature is not None or card.rack.soil_moisture is not None):
        temp = "—" if card.rack.soil_temperature is None else f"{card.rack.soil_temperature:.1f}"
        moisture = "—" if card.rack.soil_moisture is None else f"{card.rack.soil_moisture:.0f}"
        sensor = st(lang, "sensor", temp=temp, moisture=moisture)
    caption = st(lang, "plant_card", name=escape(plant_name(card.plant, lang)), day=day_number(card.planting.planted_at), rack=card.slot.rack_id, slot=card.slot.slot_number, status=escape(status_text(lang, card.planting.status)), likes=card.likes, dislikes=card.dislikes, comments=card.comments, gifts=card.gifts, gift_kisa=card.gift_kisa, sensor=sensor)
    keyboard = plant_keyboard(lang, card, index, total)
    photo_path = resolve_photo_path(card.photo)
    if photo_path:
        try:
            await bot.send_photo(chat_id, photo_path, caption=caption, reply_markup=keyboard)
            return
        except Exception:
            logger.exception("Could not send rack photo %s", photo_path)
    await bot.send_message(chat_id, caption + f"\n\n<i>{escape(st(lang, 'photo_unavailable'))}</i>", reply_markup=keyboard)


async def show_comments(bot: TelegramBotAPI, chat_id: int, tg: dict, planting_id: str, index: int) -> None:
    lang = language_for(tg)
    comments = await list_comments(planting_id, limit=10)
    text = st(lang, "comments_title")
    if not comments:
        text += "\n\n" + st(lang, "no_comments")
    else:
        for comment, user in reversed(comments):
            name = user.first_name or user.username or "KisaMore user"
            text += f"\n\n<b>{escape(name)}</b>\n{escape(comment.body)}"
    markup = {"inline_keyboard": [[{"text": st(lang, "write_comment"), "callback_data": f"comment:write:{planting_id}"}], [{"text": st(lang, "back_plants"), "callback_data": f"plant:show:{planting_id}:{index}"}]]}
    await bot.send_message(chat_id, text, reply_markup=markup)


async def show_gift_menu(bot: TelegramBotAPI, chat_id: int, tg: dict, planting_id: str, index: int) -> None:
    lang = language_for(tg)
    rows = [
        [{"text": st(lang, "gift_sprout"), "callback_data": f"gift:send:sprout:{planting_id}:{index}"}],
        [{"text": st(lang, "gift_sun"), "callback_data": f"gift:send:sun:{planting_id}:{index}"}],
        [{"text": st(lang, "gift_support"), "callback_data": f"gift:send:support:{planting_id}:{index}"}],
        [{"text": st(lang, "gift_trophy"), "callback_data": f"gift:send:trophy:{planting_id}:{index}"}],
        [{"text": st(lang, "back_plants"), "callback_data": f"plant:show:{planting_id}:{index}"}],
    ]
    await bot.send_message(chat_id, st(lang, "gift_title"), reply_markup={"inline_keyboard": rows})


async def show_community(bot: TelegramBotAPI, chat_id: int, tg: dict) -> None:
    lang = language_for(tg)
    top = await community_top(5)
    if not top:
        await bot.send_message(chat_id, st(lang, "community_empty"), reply_markup=back_keyboard(lang))
        return
    text = st(lang, "community_title")
    buttons = []
    for rank, (planting, plant, _, likes, gifts) in enumerate(top, start=1):
        name = plant_name(plant, lang)
        text += "\n" + st(lang, "community_item", rank=rank, name=escape(name), likes=likes, gifts=gifts)
        buttons.append([{"text": f"{rank}. 🌱 {name}"[:60], "callback_data": f"plant:show:{planting.id}:0"}])
    buttons.append([{"text": t(lang, "back_home"), "callback_data": "menu:home"}])
    await bot.send_message(chat_id, text, reply_markup={"inline_keyboard": buttons})


async def show_garden(bot: TelegramBotAPI, chat_id: int, tg: dict) -> None:
    lang = language_for(tg)
    user, _ = await get_or_create_user(tg)
    followed = await list_followed_plantings(user.id, 6)
    requests = await rental_requests(user.id, 6)
    allocations = await linked_allocations(user, 6)
    parts = [t(lang, "garden")]
    buttons = []
    if followed:
        parts.append("\n" + st(lang, "garden_following"))
        for planting, plant, slot in followed:
            name = plant_name(plant, lang)
            parts.append(f"• 🌱 {escape(name)} · #{slot.rack_id}/{slot.slot_number}")
            buttons.append([{"text": f"🌱 {name}"[:60], "callback_data": f"plant:show:{planting.id}:0"}])
    if requests:
        parts.append(st(lang, "garden_requests"))
        for req, slot, plant in requests:
            parts.append(st(lang, "rent_status", rack=slot.rack_id, slot=slot.slot_number, plant=escape(plant_name(plant, lang)), status=escape(st(lang, f"status_{req.status}"))))
    if allocations:
        parts.append("\n\n🪴 <b>Active allocations</b>")
        for allocation in allocations:
            parts.append(f"• Rack {allocation.rack_id} · Container {allocation.slot_number or '—'}")
    if not followed and not requests and not allocations:
        parts.append("\n" + st(lang, "garden_empty"))
    buttons.append([{"text": st(lang, "rent_button"), "callback_data": "rent:start"}])
    buttons.append([{"text": t(lang, "back_home"), "callback_data": "menu:home"}])
    await bot.send_message(chat_id, "\n".join(parts), reply_markup={"inline_keyboard": buttons})


async def show_rental_slots(bot: TelegramBotAPI, chat_id: int, tg: dict) -> None:
    lang = language_for(tg)
    slots = await list_available_slots(20)
    if not slots:
        await bot.send_message(chat_id, st(lang, "rent_no_slots"), reply_markup={"inline_keyboard": [[{"text": st(lang, "back_garden"), "callback_data": "menu:garden"}]]})
        return
    rows = [[{"text": f"🪴 #{slot.rack_id}/{slot.slot_number}", "callback_data": f"rent:slot:{slot.id}"}] for slot in slots]
    rows.append([{"text": st(lang, "back_garden"), "callback_data": "menu:garden"}])
    await bot.send_message(chat_id, st(lang, "rent_choose_slot"), reply_markup={"inline_keyboard": rows})


async def show_rental_plants(bot: TelegramBotAPI, chat_id: int, tg: dict, slot_id: int) -> None:
    lang = language_for(tg)
    slots = await list_available_slots(50)
    slot = next((item for item in slots if item.id == slot_id), None)
    if slot is None:
        await show_rental_slots(bot, chat_id, tg)
        return
    plants = await list_active_plants(20)
    rows = [[{"text": f"🌱 {plant_name(plant, lang)}"[:60], "callback_data": f"rent:plant:{slot_id}:{plant.id}"}] for plant in plants]
    rows.append([{"text": st(lang, "cancel"), "callback_data": "menu:garden"}])
    await bot.send_message(chat_id, st(lang, "rent_choose_plant", rack=slot.rack_id, slot=slot.slot_number), reply_markup={"inline_keyboard": rows})


async def credit_payment(tg: dict, payment: dict) -> tuple[bool, int, int]:
    user, _ = await get_or_create_user(tg)
    parsed = parse_payload(str(payment.get("invoice_payload", "")))
    if parsed is None:
        raise ValueError("Invalid invoice payload")
    tg_id, stars, kisa = parsed
    if tg_id != int(tg["id"]) or payment.get("currency") != "XTR" or int(payment.get("total_amount", -1)) != stars or PACKAGES.get(stars) != kisa:
        raise ValueError("Invalid payment parameters")
    charge_id = str(payment["telegram_payment_charge_id"])
    async with SessionLocal() as session:
        existing = await session.execute(select(StarPayment).where(StarPayment.telegram_payment_charge_id == charge_id))
        if existing.scalar_one_or_none() is not None:
            wallet = await wallet_for_update(session, user.id)
            return False, wallet.balance, kisa
        wallet = await wallet_for_update(session, user.id)
        wallet.balance += kisa
        session.add(StarPayment(user_id=user.id, telegram_payment_charge_id=charge_id, provider_payment_charge_id=payment.get("provider_payment_charge_id") or None, invoice_payload=str(payment["invoice_payload"]), stars_amount=stars, kisa_amount=kisa, status="paid"))
        session.add(WalletTransaction(user_id=user.id, amount=kisa, balance_after=wallet.balance, kind="stars_purchase", reference_type="telegram_payment", reference_id=charge_id, details={"stars": stars, "currency": "XTR"}))
        await session.commit()
        return True, wallet.balance, kisa


async def handle_state_message(bot: TelegramBotAPI, message: dict, tg: dict, user: TelegramUser) -> bool:
    lang = language_for(tg)
    text = (message.get("text") or "").strip()
    state = await get_state(user.id)
    if state is None:
        return False
    if text.lower().split("@", 1)[0] == "/cancel":
        await clear_state(user.id)
        await bot.send_message(message["chat"]["id"], st(lang, "comment_cancelled"), reply_markup=main_keyboard(lang))
        return True
    if text.startswith("/"):
        return False
    if state.mode == "comment" and state.target_type == "planting" and state.target_id:
        try:
            await add_comment(user.id, state.target_id, text)
        except ValueError as exc:
            if str(exc) == "too_long":
                await bot.send_message(message["chat"]["id"], st(lang, "comment_too_long"))
                return True
            await clear_state(user.id)
            return False
        target_id = state.target_id
        await clear_state(user.id)
        await bot.send_message(message["chat"]["id"], st(lang, "comment_saved"))
        await show_plant_card(bot, message["chat"]["id"], tg, target_id, index=0)
        return True
    return False


async def handle_message(bot: TelegramBotAPI, message: dict) -> None:
    tg = message.get("from")
    chat_id = (message.get("chat") or {}).get("id")
    if tg is None or chat_id is None:
        return
    lang = language_for(tg)
    user, _ = await get_or_create_user(tg)
    if message.get("successful_payment"):
        try:
            credited, balance, kisa = await credit_payment(tg, message["successful_payment"])
            if credited:
                await bot.send_message(chat_id, t(lang, "payment_received", kisa=kisa, balance=balance), reply_markup=main_keyboard(lang))
        except Exception:
            logger.exception("Failed to credit Stars payment")
            await bot.send_message(chat_id, t(lang, "payment_processing_error"))
        return
    if await handle_state_message(bot, message, tg, user):
        return
    text = (message.get("text") or "").strip()
    command = text.split(maxsplit=1)[0].split("@", 1)[0].lower()
    if command in {"/start", "/menu"}:
        await show_home(bot, chat_id, tg)
    elif command == "/wallet":
        await show_wallet(bot, chat_id, tg)
    elif command == "/profile":
        await show_profile(bot, chat_id, tg)
    elif command == "/plants":
        await show_plant_at(bot, chat_id, tg, 0)
    elif command == "/garden":
        await show_garden(bot, chat_id, tg)
    elif command == "/terms":
        await bot.send_message(chat_id, t(lang, "terms"), reply_markup=terms_keyboard(lang))
    elif command in {"/paysupport", "/support"}:
        contact = escape(settings.telegram_support_contact) if settings.telegram_support_contact else t(lang, "support_not_configured")
        await bot.send_message(chat_id, f"{t(lang, 'payment_support_title')}\n\n{contact}")
    elif command == "/help":
        await bot.send_message(chat_id, t(lang, "help"), reply_markup=back_keyboard(lang))
    elif command == "/cancel":
        await clear_state(user.id)
        await show_home(bot, chat_id, tg)
    else:
        await show_home(bot, chat_id, tg)


async def handle_callback(bot: TelegramBotAPI, query: dict) -> None:
    qid = query.get("id")
    tg = query.get("from")
    chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
    data = str(query.get("data") or "")
    if not qid or tg is None or chat_id is None:
        return
    lang = language_for(tg)
    user, _ = await get_or_create_user(tg)
    if data == "menu:home":
        await bot.answer_callback_query(qid); await show_home(bot, chat_id, tg)
    elif data == "menu:wallet":
        await bot.answer_callback_query(qid); await show_wallet(bot, chat_id, tg)
    elif data == "menu:profile":
        await bot.answer_callback_query(qid); await show_profile(bot, chat_id, tg)
    elif data == "menu:plants":
        await bot.answer_callback_query(qid); await show_plant_at(bot, chat_id, tg, 0)
    elif data == "menu:garden":
        await bot.answer_callback_query(qid); await show_garden(bot, chat_id, tg)
    elif data == "menu:community":
        await bot.answer_callback_query(qid); await show_community(bot, chat_id, tg)
    elif data.startswith("feed:"):
        await bot.answer_callback_query(qid)
        try: index = int(data.split(":", 1)[1])
        except ValueError: index = 0
        await show_plant_at(bot, chat_id, tg, index)
    elif data.startswith("plant:show:"):
        await bot.answer_callback_query(qid)
        parts = data.split(":")
        if len(parts) >= 4:
            try: index = int(parts[3])
            except ValueError: index = 0
            await show_plant_card(bot, chat_id, tg, parts[2], index=index, user_id=user.id)
    elif data.startswith("vote:"):
        parts = data.split(":")
        if len(parts) >= 4:
            result = await toggle_vote(user.id, parts[2], parts[1])
            await bot.answer_callback_query(qid, text=st(lang, "vote_set" if result else "vote_removed"))
        else: await bot.answer_callback_query(qid)
    elif data.startswith("follow:"):
        parts = data.split(":")
        if len(parts) >= 3:
            enabled = await toggle_follow(user.id, parts[1])
            await bot.answer_callback_query(qid, text=st(lang, "followed" if enabled else "unfollowed"))
        else: await bot.answer_callback_query(qid)
    elif data.startswith("comment:write:"):
        planting_id = data.split(":", 2)[2]
        await set_state(user.id, "comment", target_type="planting", target_id=planting_id)
        await bot.answer_callback_query(qid)
        await bot.send_message(chat_id, st(lang, "comment_prompt"))
    elif data.startswith("comment:list:"):
        parts = data.split(":"); await bot.answer_callback_query(qid)
        if len(parts) >= 4:
            try: index = int(parts[3])
            except ValueError: index = 0
            await show_comments(bot, chat_id, tg, parts[2], index)
    elif data.startswith("gift:menu:"):
        parts = data.split(":"); await bot.answer_callback_query(qid)
        if len(parts) >= 4:
            try: index = int(parts[3])
            except ValueError: index = 0
            await show_gift_menu(bot, chat_id, tg, parts[2], index)
    elif data.startswith("gift:send:"):
        parts = data.split(":")
        if len(parts) >= 5:
            ok, balance, cost = await send_gift(user.id, parts[3], parts[2])
            await bot.answer_callback_query(qid, text=st(lang, "gift_sent", cost=cost, balance=balance) if ok else st(lang, "not_enough_kisa", balance=balance), show_alert=not ok)
        else: await bot.answer_callback_query(qid)
    elif data.startswith("timelapse:"):
        await bot.answer_callback_query(qid); await bot.send_message(chat_id, st(lang, "timelapse_unavailable"))
    elif data == "rent:start":
        await bot.answer_callback_query(qid); await show_rental_slots(bot, chat_id, tg)
    elif data.startswith("rent:slot:"):
        await bot.answer_callback_query(qid)
        try: slot_id = int(data.rsplit(":", 1)[1])
        except ValueError: return
        await show_rental_plants(bot, chat_id, tg, slot_id)
    elif data.startswith("rent:plant:"):
        parts = data.split(":", 3); await bot.answer_callback_query(qid)
        if len(parts) == 4:
            try: slot_id = int(parts[2])
            except ValueError: return
            try:
                await create_rental_request(user.id, slot_id, parts[3]); await bot.send_message(chat_id, st(lang, "rent_requested"))
            except ValueError:
                await bot.send_message(chat_id, st(lang, "rent_no_slots"))
            await show_garden(bot, chat_id, tg)
    elif data == "terms:show":
        await bot.answer_callback_query(qid); await bot.send_message(chat_id, t(lang, "terms"), reply_markup=terms_keyboard(lang))
    elif data == "terms:accept":
        await bot.answer_callback_query(qid)
        async with SessionLocal() as session:
            db_user = (await session.execute(select(TelegramUser).where(TelegramUser.id == user.id))).scalar_one()
            if db_user.terms_accepted_at is None:
                db_user.terms_accepted_at = datetime.now(timezone.utc); await session.commit()
        await bot.send_message(chat_id, t(lang, "terms_accepted")); await show_wallet(bot, chat_id, tg)
    elif data.startswith("wallet:buy:"):
        await bot.answer_callback_query(qid)
        if not user.terms_accepted_at:
            await bot.send_message(chat_id, t(lang, "terms"), reply_markup=terms_keyboard(lang, wallet_back=False)); return
        try: stars = int(data.rsplit(":", 1)[-1])
        except ValueError: return
        kisa = PACKAGES.get(stars)
        if kisa is None: return
        await bot.send_invoice(chat_id, title=f"{kisa} Kisa", description=t(lang, "invoice_description", kisa=kisa), payload=invoice_payload(int(tg["id"]), stars, kisa), stars=stars)
    else:
        await bot.answer_callback_query(qid)


async def handle_pre_checkout(bot: TelegramBotAPI, query: dict) -> None:
    qid = query.get("id"); tg = query.get("from"); parsed = parse_payload(str(query.get("invoice_payload") or "")); valid = False; lang = language_for(tg)
    if qid and tg and parsed:
        user, _ = await get_or_create_user(tg); tg_id, stars, kisa = parsed
        valid = bool(user.terms_accepted_at and tg_id == int(tg["id"]) and query.get("currency") == "XTR" and int(query.get("total_amount", -1)) == stars and PACKAGES.get(stars) == kisa)
    if qid:
        await bot.answer_pre_checkout_query(qid, ok=valid, error_message=None if valid else t(lang, "precheckout_error"))


async def handle_update(bot: TelegramBotAPI, update: dict) -> None:
    if "pre_checkout_query" in update: await handle_pre_checkout(bot, update["pre_checkout_query"])
    elif "callback_query" in update: await handle_callback(bot, update["callback_query"])
    elif "message" in update: await handle_message(bot, update["message"])


async def follow_notification_loop(bot: TelegramBotAPI) -> None:
    while True:
        try:
            for item in await pending_follow_notifications(50):
                lang = language_for({"language_code": item.language_code})
                name = localized_value(item.plant_name_values, lang, "Plant")
                text = st(lang, "new_photo", name=escape(name), rack=item.rack_id, slot=item.slot_number)
                markup = {"inline_keyboard": [[{"text": st(lang, "open_plant"), "callback_data": f"plant:show:{item.planting_id}:0"}]]}
                path = resolve_photo_path(item.photo)
                try:
                    if path: await bot.send_photo(item.telegram_user_id, path, caption=text, reply_markup=markup)
                    else: await bot.send_message(item.telegram_user_id, text, reply_markup=markup)
                    await mark_follow_notified(item.follow_id, item.photo.updated_at)
                except Exception:
                    logger.exception("Failed to send follow notification to %s", item.telegram_user_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Follow notification loop failed")
        await asyncio.sleep(60)


async def run() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("KISAMORE_TELEGRAM_BOT_TOKEN is not configured")
    await create_tables()
    bot = TelegramBotAPI(settings.telegram_bot_token)
    await bot.prepare_long_polling()
    logger.info("KisaMore Telegram bot started: @%s", settings.telegram_bot_username)
    notification_task = asyncio.create_task(follow_notification_loop(bot))
    offset = None
    try:
        while True:
            try:
                for update in await bot.get_updates(offset=offset, timeout_seconds=30):
                    update_id = int(update["update_id"])
                    try: await handle_update(bot, update)
                    except Exception: logger.exception("Failed to process Telegram update %s", update_id)
                    offset = update_id + 1
            except asyncio.CancelledError: raise
            except Exception:
                logger.exception("Telegram polling failed; retrying"); await asyncio.sleep(3)
    finally:
        notification_task.cancel()
        try: await notification_task
        except asyncio.CancelledError: pass
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
