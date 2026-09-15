from __future__ import annotations

from . import find_plant_game as find_game
from . import gamification as game


async def _fallback_game_menu(core, bot, chat_id: int, tg: dict) -> None:
    """Render the original daily game even if an optional game extension fails."""
    lang = core.language_for(tg)
    tr = game._tr(lang)
    user, _ = await core.get_or_create_user(tg)
    snapshot = await game._snapshot(user.id)
    remaining = max(0, snapshot["target"] - snapshot["balance"])

    text = (
        f"{tr['title']}\n\n{tr['done'] if snapshot['reward_done'] else tr['open']}\n\n"
        f"{game._task(tr['likes'], snapshot['likes'], game.LIKE_TARGET, snapshot['likes_done'])}\n"
        f"{game._task(tr['comments'], snapshot['comments'], game.COMMENT_TARGET, snapshot['comments_done'])}\n"
        f"{'✅' if snapshot['quiz_done'] else '▫️'} {tr['quiz']}\n\n"
        f"{tr['streak'].format(days=snapshot['streak'])}\n"
        f"{tr['xp'].format(xp=snapshot['xp'], level=game._level(snapshot['xp'], lang))}\n\n"
        f"{tr['goal'].format(balance=snapshot['balance'], target=snapshot['target'])}\n"
        f"<code>{game._bar(snapshot['balance'], snapshot['target'])}</code>\n"
        f"{tr['goal_ready'] if remaining == 0 else tr['goal_days'].format(days=remaining)}"
    )

    await bot.send_message(
        chat_id,
        text,
        reply_markup={
            "inline_keyboard": [
                [{"text": tr["quiz_button"], "callback_data": "game:quiz"}],
                [{"text": tr["plants_button"], "callback_data": "menu:plants"}],
                [{"text": tr["back"], "callback_data": "menu:home"}],
            ]
        },
    )


def install(core) -> None:
    previous_handle_callback = core.handle_callback
    original_status = find_game._status

    async def safe_status(user_id: int) -> dict:
        try:
            return await original_status(user_id)
        except Exception:
            core.logger.exception(
                "Find-your-plant status check failed for Telegram user %s; game menu remains available",
                user_id,
            )
            return {"available": False, "done": False}

    # _extended_game_menu resolves _status from the module at runtime.
    find_game._status = safe_status

    async def handle_callback(bot, query: dict) -> None:
        data = str(query.get("data") or "")

        if data == "game:menu":
            qid = query.get("id")
            tg = query.get("from")
            chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
            if not qid or tg is None or chat_id is None:
                return
            await bot.answer_callback_query(qid)
            try:
                await find_game._extended_game_menu(core, bot, chat_id, tg)
            except Exception:
                core.logger.exception(
                    "Extended Telegram game menu failed; rendering base game menu"
                )
                await _fallback_game_menu(core, bot, chat_id, tg)
            return

        if data == "game:find" or data.startswith("game:findanswer:"):
            tg = query.get("from")
            chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
            qid = query.get("id")
            try:
                await previous_handle_callback(bot, query)
            except Exception:
                core.logger.exception("Find-your-plant callback failed: %s", data)
                if qid:
                    try:
                        await bot.answer_callback_query(qid)
                    except Exception:
                        pass
                if tg is not None and chat_id is not None:
                    lang = core.language_for(tg)
                    tr = find_game._tr(lang)
                    await bot.send_message(
                        chat_id,
                        tr["unavailable"],
                        reply_markup={
                            "inline_keyboard": [[
                                {"text": tr["game"], "callback_data": "game:menu"}
                            ]]
                        },
                    )
            return

        await previous_handle_callback(bot, query)

    core.handle_callback = handle_callback
