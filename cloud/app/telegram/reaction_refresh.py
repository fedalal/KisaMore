from __future__ import annotations

from html import escape


def _plant_caption(core, lang: str, card) -> str:
    sensor = ""
    if card.rack and (
        card.rack.soil_temperature is not None
        or card.rack.soil_moisture is not None
    ):
        temp = (
            "—"
            if card.rack.soil_temperature is None
            else f"{card.rack.soil_temperature:.1f}"
        )
        moisture = (
            "—"
            if card.rack.soil_moisture is None
            else f"{card.rack.soil_moisture:.0f}"
        )
        sensor = core.st(lang, "sensor", temp=temp, moisture=moisture)

    return core.st(
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


async def _refresh_source_message(
    core,
    bot,
    query: dict,
    *,
    user_id: int,
    planting_id: str,
    index: int,
) -> None:
    """Refresh the plant card in-place after a like/dislike toggle."""
    message = query.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")
    if chat_id is None or message_id is None:
        return

    card = await core.get_plant_card(planting_id, user_id)
    if card is None:
        return

    total = max(1, len(await core.list_plantings(limit=20)))
    index = max(0, min(index, total - 1))
    lang = core.language_for(query.get("from") or {})
    caption = _plant_caption(core, lang, card)
    keyboard = core.plant_keyboard(lang, card, index, total)

    if message.get("photo"):
        await bot.call(
            "editMessageCaption",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": keyboard,
            },
        )
        return

    text = caption + f"\n\n<i>{escape(core.st(lang, 'photo_unavailable'))}</i>"
    await bot.call(
        "editMessageText",
        {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
            "reply_markup": keyboard,
        },
    )


def install(core) -> None:
    previous_handle_callback = core.handle_callback

    async def handle_callback(bot, query: dict) -> None:
        data = str(query.get("data") or "")
        if not data.startswith("vote:"):
            await previous_handle_callback(bot, query)
            return

        qid = query.get("id")
        tg = query.get("from")
        message = query.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        if not qid or tg is None or chat_id is None:
            return

        parts = data.split(":")
        if len(parts) < 4 or parts[1] not in ("like", "dislike"):
            await bot.answer_callback_query(qid)
            return

        planting_id = parts[2]
        try:
            index = int(parts[3])
        except ValueError:
            index = 0

        user, _ = await core.get_or_create_user(tg)
        result = await core.toggle_vote(user.id, planting_id, parts[1])
        lang = core.language_for(tg)

        # Acknowledge the tap immediately; refreshing the card can take another
        # request to Telegram and should not keep the callback spinner visible.
        await bot.answer_callback_query(
            qid,
            text=core.st(lang, "vote_set" if result else "vote_removed"),
        )

        try:
            await _refresh_source_message(
                core,
                bot,
                query,
                user_id=user.id,
                planting_id=planting_id,
                index=index,
            )
        except Exception:
            # The vote is already stored. A failed UI refresh must not undo it
            # or make the whole bot callback fail.
            core.logger.exception(
                "Could not refresh Telegram plant card after reaction: planting=%s",
                planting_id,
            )

    core.handle_callback = handle_callback
