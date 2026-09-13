from __future__ import annotations

from html import escape


FOLLOW_UI = {
    "en": {
        "subscribe": "Subscribe",
        "unsubscribe": "Unsubscribe",
        "subscribed": (
            "✅ <b>You are subscribed to updates for this plant.</b>\n\n"
            "I will send you a new photo when one appears. "
            "You can also find this plant in <b>My garden</b>."
        ),
        "unsubscribed": (
            "🔕 <b>You have unsubscribed from this plant.</b>\n\n"
            "You will no longer receive new-photo notifications for it."
        ),
    },
    "ru": {
        "subscribe": "Подписаться",
        "unsubscribe": "Отписаться",
        "subscribed": (
            "✅ <b>Вы подписались на обновления этого растения.</b>\n\n"
            "Я пришлю вам новую фотографию, когда она появится. "
            "Растение также будет доступно в разделе <b>«Мой сад»</b>."
        ),
        "unsubscribed": (
            "🔕 <b>Вы отписались от обновлений этого растения.</b>\n\n"
            "Новые фотографии этого растения больше не будут приходить."
        ),
    },
    "de": {
        "subscribe": "Abonnieren",
        "unsubscribe": "Abbestellen",
        "subscribed": (
            "✅ <b>Du hast die Updates für diese Pflanze abonniert.</b>\n\n"
            "Ich sende dir ein neues Foto, sobald eines verfügbar ist. "
            "Die Pflanze findest du außerdem unter <b>Mein Garten</b>."
        ),
        "unsubscribed": (
            "🔕 <b>Du hast die Updates für diese Pflanze abbestellt.</b>\n\n"
            "Du erhältst keine Benachrichtigungen über neue Fotos mehr."
        ),
    },
    "fr": {
        "subscribe": "S’abonner",
        "unsubscribe": "Se désabonner",
        "subscribed": (
            "✅ <b>Vous êtes abonné aux mises à jour de cette plante.</b>\n\n"
            "Je vous enverrai une nouvelle photo dès qu’elle sera disponible. "
            "Vous retrouverez aussi cette plante dans <b>Mon jardin</b>."
        ),
        "unsubscribed": (
            "🔕 <b>Vous vous êtes désabonné de cette plante.</b>\n\n"
            "Vous ne recevrez plus de notifications lors de nouvelles photos."
        ),
    },
    "es": {
        "subscribe": "Suscribirse",
        "unsubscribe": "Cancelar suscripción",
        "subscribed": (
            "✅ <b>Te has suscrito a las actualizaciones de esta planta.</b>\n\n"
            "Te enviaré una foto nueva cuando aparezca. "
            "También podrás encontrar esta planta en <b>Mi jardín</b>."
        ),
        "unsubscribed": (
            "🔕 <b>Has cancelado la suscripción a esta planta.</b>\n\n"
            "Ya no recibirás avisos cuando haya fotos nuevas."
        ),
    },
    "it": {
        "subscribe": "Iscriviti",
        "unsubscribe": "Annulla iscrizione",
        "subscribed": (
            "✅ <b>Ti sei iscritto agli aggiornamenti di questa pianta.</b>\n\n"
            "Ti invierò una nuova foto quando sarà disponibile. "
            "Troverai inoltre questa pianta in <b>Il mio giardino</b>."
        ),
        "unsubscribed": (
            "🔕 <b>Hai annullato l’iscrizione a questa pianta.</b>\n\n"
            "Non riceverai più notifiche quando saranno disponibili nuove foto."
        ),
    },
    "pt": {
        "subscribe": "Subscrever",
        "unsubscribe": "Cancelar subscrição",
        "subscribed": (
            "✅ <b>Subscreveu as atualizações desta planta.</b>\n\n"
            "Vou enviar uma nova fotografia quando estiver disponível. "
            "Também poderá encontrar esta planta em <b>O meu jardim</b>."
        ),
        "unsubscribed": (
            "🔕 <b>Cancelou a subscrição desta planta.</b>\n\n"
            "Deixará de receber notificações quando houver novas fotografias."
        ),
    },
    "pl": {
        "subscribe": "Subskrybuj",
        "unsubscribe": "Anuluj subskrypcję",
        "subscribed": (
            "✅ <b>Subskrybujesz aktualizacje tej rośliny.</b>\n\n"
            "Wyślę Ci nowe zdjęcie, gdy tylko się pojawi. "
            "Roślinę znajdziesz również w sekcji <b>Mój ogród</b>."
        ),
        "unsubscribed": (
            "🔕 <b>Anulowano subskrypcję tej rośliny.</b>\n\n"
            "Nie będziesz już otrzymywać powiadomień o nowych zdjęciach."
        ),
    },
    "zh": {
        "subscribe": "订阅",
        "unsubscribe": "取消订阅",
        "subscribed": (
            "✅ <b>你已订阅这株植物的更新。</b>\n\n"
            "有新照片时，我会第一时间发送给你。"
            "你也可以在<b>我的花园</b>中找到这株植物。"
        ),
        "unsubscribed": (
            "🔕 <b>你已取消订阅这株植物。</b>\n\n"
            "以后将不再收到这株植物的新照片通知。"
        ),
    },
}


def _follow_text(lang: str, key: str) -> str:
    values = FOLLOW_UI.get(lang) or FOLLOW_UI["en"]
    return values.get(key) or FOLLOW_UI["en"][key]


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
    """Refresh the source plant card in-place after an interactive toggle."""
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
    previous_plant_keyboard = core.plant_keyboard

    def plant_keyboard(lang: str, card, index: int, total: int) -> dict:
        keyboard = previous_plant_keyboard(lang, card, index, total)
        rows = keyboard.get("inline_keyboard") or []
        for row in rows:
            for button in row:
                callback = str(button.get("callback_data") or "")
                if callback.startswith("follow:"):
                    button["text"] = _follow_text(
                        lang,
                        "unsubscribe" if card.following else "subscribe",
                    )
        return keyboard

    core.plant_keyboard = plant_keyboard

    async def handle_callback(bot, query: dict) -> None:
        data = str(query.get("data") or "")
        if not (data.startswith("vote:") or data.startswith("follow:")):
            await previous_handle_callback(bot, query)
            return

        qid = query.get("id")
        tg = query.get("from")
        message = query.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        if not qid or tg is None or chat_id is None:
            return

        parts = data.split(":")
        user, _ = await core.get_or_create_user(tg)
        lang = core.language_for(tg)

        if data.startswith("vote:"):
            if len(parts) < 4 or parts[1] not in ("like", "dislike"):
                await bot.answer_callback_query(qid)
                return
            planting_id = parts[2]
            try:
                index = int(parts[3])
            except ValueError:
                index = 0

            result = await core.toggle_vote(user.id, planting_id, parts[1])
            await bot.answer_callback_query(
                qid,
                text=core.st(lang, "vote_set" if result else "vote_removed"),
            )

        else:
            if len(parts) < 3:
                await bot.answer_callback_query(qid)
                return
            planting_id = parts[1]
            try:
                index = int(parts[2])
            except ValueError:
                index = 0

            enabled = await core.toggle_follow(user.id, planting_id)
            await bot.answer_callback_query(qid)

            # Explain exactly what the subscription means. This is a normal
            # Telegram message (not just a short callback toast), so the user
            # can refer back to it later.
            await bot.send_message(
                chat_id,
                _follow_text(lang, "subscribed" if enabled else "unsubscribed"),
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
            # The database change is already stored. A failed UI refresh must
            # not undo it or make the whole callback fail.
            core.logger.exception(
                "Could not refresh Telegram plant card after toggle: planting=%s",
                planting_id,
            )

    core.handle_callback = handle_callback
