from __future__ import annotations

from .i18n import language_for
from .reaction_refresh import FOLLOW_UI
from .service import get_or_create_user, send_gift
from .social_i18n import TEXT as SOCIAL_TEXT, st


GIFT_SUCCESS = {
    "en": "🎁 <b>Gift sent successfully!</b>\n\n🪙 Your balance is: <b>{balance} Ⓚ</b>",
    "ru": "🎁 <b>Подарок успешно отправлен!</b>\n\n🪙 Ваш баланс составляет: <b>{balance} Ⓚ</b>",
    "de": "🎁 <b>Geschenk erfolgreich gesendet!</b>\n\n🪙 Dein Guthaben beträgt: <b>{balance} Ⓚ</b>",
    "fr": "🎁 <b>Cadeau envoyé avec succès !</b>\n\n🪙 Votre solde est de : <b>{balance} Ⓚ</b>",
    "es": "🎁 <b>¡Regalo enviado correctamente!</b>\n\n🪙 Tu saldo es: <b>{balance} Ⓚ</b>",
    "it": "🎁 <b>Regalo inviato con successo!</b>\n\n🪙 Il tuo saldo è: <b>{balance} Ⓚ</b>",
    "pt": "🎁 <b>Presente enviado com sucesso!</b>\n\n🪙 O seu saldo é: <b>{balance} Ⓚ</b>",
    "pl": "🎁 <b>Prezent został wysłany!</b>\n\n🪙 Twoje saldo wynosi: <b>{balance} Ⓚ</b>",
    "zh": "🎁 <b>礼物已成功送出！</b>\n\n🪙 您的余额为：<b>{balance} Ⓚ</b>",
}


def _success_text(lang: str, balance: int) -> str:
    template = GIFT_SUCCESS.get(lang) or GIFT_SUCCESS["en"]
    return template.format(balance=balance)


def _install_follow_icons() -> None:
    """Keep the subscription action visually distinct in every locale."""
    for values in FOLLOW_UI.values():
        subscribe = str(values.get("subscribe") or "")
        unsubscribe = str(values.get("unsubscribe") or "")
        if subscribe and not subscribe.startswith("🔔"):
            values["subscribe"] = f"🔔 {subscribe}"
        if unsubscribe and not unsubscribe.startswith("🔕"):
            values["unsubscribe"] = f"🔕 {unsubscribe}"


def _install_kisa_symbol() -> None:
    """Use the compact Ⓚ currency symbol in the gift flow copy."""
    for values in SOCIAL_TEXT.values():
        gift_title = values.get("gift_title")
        if gift_title:
            values["gift_title"] = str(gift_title).replace("Kisa", "Ⓚ")


def install(core) -> None:
    _install_follow_icons()
    _install_kisa_symbol()
    previous_handle_callback = core.handle_callback

    async def handle_callback(bot, query: dict) -> None:
        data = str(query.get("data") or "")
        if not data.startswith("gift:send:"):
            await previous_handle_callback(bot, query)
            return

        qid = query.get("id")
        tg = query.get("from")
        chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
        if not qid or tg is None or chat_id is None:
            return

        parts = data.split(":")
        if len(parts) < 5:
            await bot.answer_callback_query(qid)
            return

        user, _ = await get_or_create_user(tg)
        lang = language_for(tg)
        ok, balance, _cost = await send_gift(user.id, parts[3], parts[2])

        if not ok:
            await bot.answer_callback_query(
                qid,
                text=st(lang, "not_enough_kisa", balance=balance),
                show_alert=True,
            )
            return

        # A successful gift deserves a persistent confirmation instead of the
        # short-lived callback toast. This also makes the remaining balance easy
        # to find after the popup disappears.
        await bot.answer_callback_query(qid)
        await bot.send_message(chat_id, _success_text(lang, balance))

    core.handle_callback = handle_callback
