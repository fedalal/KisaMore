from __future__ import annotations

from datetime import timezone
from html import escape

from sqlalchemy import func, select

from ..db import SessionLocal
from ..models import Allocation
from .models import SocialFollow, TelegramUser


async def _follower_count(planting_id: str) -> int:
    async with SessionLocal() as session:
        value = (
            await session.execute(
                select(func.count(SocialFollow.id)).where(
                    SocialFollow.target_type == "planting",
                    SocialFollow.target_id == planting_id,
                )
            )
        ).scalar_one()
    return int(value or 0)


def _date_text(value) -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _growth_days(start, end) -> int:
    if start is None or end is None:
        return 0
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if end < start:
        return 0
    return max(1, int((end - start).total_seconds() // 86400) + 1)


def build_plant_caption(core, lang: str, card) -> str:
    """Build a live or immutable historical planting caption."""
    if card.planting.status == "harvested":
        caption = core.st(
            lang,
            "historical_plant_card",
            name=escape(core.plant_name(card.plant, lang)),
            planted=_date_text(card.planting.planted_at),
            harvested=_date_text(card.planting.actual_harvest_at),
            days=_growth_days(
                card.planting.planted_at,
                card.planting.actual_harvest_at,
            ),
            rack=card.slot.rack_id,
            slot=card.slot.slot_number,
            likes=card.likes,
            dislikes=card.dislikes,
            comments=card.comments,
            gifts=card.gifts,
            gift_kisa=card.gift_kisa,
        )
        followers = int(getattr(card, "followers", 0) or 0)
        stats = f"❤️ {card.likes}   👎 {card.dislikes}   💬 {card.comments}"
        stats_with_followers = f"{stats}   🔔 {followers}"
        if stats in caption:
            caption = caption.replace(stats, stats_with_followers, 1)
        return caption

    sensor = ""
    if card.rack and card.rack.soil_temperature is not None:
        sensor = f"\n\n🌡 {card.rack.soil_temperature:.1f}°C"

    caption = core.st(
        lang,
        "plant_card",
        name=escape(core.plant_name(card.plant, lang)),
        day=core.day_number(card.planting.planted_at),
        rack=card.slot.rack_id,
        slot=card.slot.slot_number,
        status=escape(core.status_text(lang, card.planting.status)),
        likes=card.likes,
        dislikes=card.dislikes,
        comments=card.comments,
        gifts=card.gifts,
        gift_kisa=card.gift_kisa,
        sensor=sensor,
    )

    followers = int(getattr(card, "followers", 0) or 0)
    stats = f"❤️ {card.likes}   👎 {card.dislikes}   💬 {card.comments}"
    stats_with_followers = f"{stats}   🔔 {followers}"
    if stats in caption:
        caption = caption.replace(stats, stats_with_followers, 1)
    return caption


def install(core) -> None:
    previous_get_plant_card = core.get_plant_card

    async def get_plant_card(planting_id: str, user_id: int):
        card = await previous_get_plant_card(planting_id, user_id)
        if card is not None:
            card.followers = await _follower_count(planting_id)
            card.is_owner = False
            allocation_id = getattr(card.planting, "cloud_allocation_id", None)
            if allocation_id:
                async with SessionLocal() as session:
                    telegram_user = await session.get(TelegramUser, user_id)
                    allocation = await session.get(Allocation, allocation_id)
                    card.is_owner = bool(
                        telegram_user is not None
                        and telegram_user.marketplace_user_id
                        and allocation is not None
                        and allocation.status == "active"
                        and allocation.user_id == telegram_user.marketplace_user_id
                    )
        return card

    async def show_plant_card(
        bot,
        chat_id: int,
        tg: dict,
        planting_id: str,
        *,
        index: int = 0,
        total: int | None = None,
        user_id: int | None = None,
    ) -> None:
        lang = core.language_for(tg)
        if user_id is None:
            user, _ = await core.get_or_create_user(tg)
            user_id = user.id

        card = await get_plant_card(planting_id, user_id)
        if card is None:
            await core.show_plant_at(bot, chat_id, tg, 0)
            return

        if card.planting.status == "harvested":
            # A historical card is not part of the live feed. Do not show
            # Previous/Next buttons that could jump to the current crop in the
            # same physical slot.
            index = 0
            total = 1
        elif total is None:
            total = max(1, len(await core.list_plantings(limit=20)))

        caption = build_plant_caption(core, lang, card)
        keyboard = core.plant_keyboard(lang, card, index, total)
        photo_path = core.resolve_photo_path(card.photo)
        if photo_path:
            try:
                await bot.send_photo(
                    chat_id,
                    photo_path,
                    caption=caption,
                    reply_markup=keyboard,
                )
                return
            except Exception:
                core.logger.exception("Could not send rack photo %s", photo_path)

        await bot.send_message(
            chat_id,
            caption + f"\n\n<i>{escape(core.st(lang, 'photo_unavailable'))}</i>",
            reply_markup=keyboard,
        )

    core.get_plant_card = get_plant_card
    core.show_plant_card = show_plant_card
    core.build_plant_caption = lambda lang, card: build_plant_caption(core, lang, card)

    # reaction_refresh edits an already displayed Telegram message after likes,
    # dislikes and subscription toggles. Make it use the exact same caption
    # builder so the follower counter and hidden moisture stay in sync there too.
    from . import reaction_refresh

    reaction_refresh._plant_caption = build_plant_caption
