"""Plant Battle browsing and joining inside Telegram.

The native checkout delegates to the existing website join_battle business
operation. It therefore shares participant limits, the Kisa ledger, row locks
and automatic ready-to-plant notifications with the website and Android.
"""
from __future__ import annotations

from collections import Counter
from html import escape
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from ..battle_api import JoinBattleIn, join_battle
from ..battle_models import PlantBattle, PlantBattleEntry
from ..db import SessionLocal
from ..models import Plant, User
from ..rental_admin_api import _ensure_marketplace_user
from . import worker_core as core
from .battle_player import open_callback
from .models import TelegramUser, WalletAccount


COPY = {
    "ru": {
        "title": "🏆 <b>Битвы растений</b>",
        "intro": "Шесть одинаковых растений. Одинаковые ресурсы. Только вы решаете, когда поливать, добавлять питание и затенять.",
        "open": "🟢 Открыт набор", "growing": "🌱 Растут", "ready_to_plant": "🌱 Ожидает посадки",
        "planting": "🌱 Посадка", "judging": "🏅 Подведение итогов",
        "finished": "🏁 Завершена", "cancelled": "Отменена", "full": "Мест нет",
        "vacant": "Свободных мест", "price": "Участие", "prize": "Приз",
        "wallet": "Баланс", "join": "🏆 Участвовать", "mine": "🌱 Мои растения",
        "watch": "👀 Смотреть битвы", "details": "Подробнее", "none": "Пока нет доступных битв.",
        "no_open": "Сейчас нет битв с открытой записью. Можно наблюдать за текущими.",
        "confirm_title": "🏆 <b>Подтвердите участие</b>",
        "confirm": "✅ Подтвердить и оплатить", "back": "◀️ К битвам",
        "confirm_hint": "После подтверждения с вашего кошелька будет списана стоимость участия. В каждой битве можно занять только один контейнер.",
        "success": "✅ <b>Вы участвуете!</b>", "container": "Ваш контейнер",
        "charged": "Списано", "balance": "Остаток Kisa",
        "insufficient": "Недостаточно Kisa. Стоимость: Ⓚ {price}, ваш баланс: Ⓚ {balance}.",
        "buy": "⭐ Пополнить Kisa", "already": "Вы уже участвуете в этой битве.",
        "closed": "Запись закрыта или свободных мест больше нет.",
        "try_again": "Не получилось оформить участие. Попробуйте позже.",
        "private": "Для участия откройте личный чат с @KisaMoreBot.",
        "terms": "Перед оплатой необходимо принять условия использования KisaMore.",
        "accept": "📄 Условия и принятие",
        "status": "Статус", "rack": "Полка", "places": "Участников",
        "entry": "Контейнер", "view": "🌱 Моё растение",
        "history": "Последние битвы", "first": "Чтобы участвовать, откройте /battle.",
        "account": "Кошелёк Kisa",
    },
    "en": {
        "title": "🏆 <b>Plant Battles</b>",
        "intro": "Six identical plants with equal resources. You choose when to water, add nutrients or shade.",
        "open": "🟢 Registration open", "growing": "🌱 Growing", "ready_to_plant": "🌱 Awaiting planting",
        "planting": "🌱 Planting", "judging": "🏅 Judging",
        "finished": "🏁 Finished", "cancelled": "Cancelled", "full": "Full",
        "vacant": "Places left", "price": "Entry", "prize": "Prize",
        "wallet": "Balance", "join": "🏆 Join Battle", "mine": "🌱 My Battles",
        "watch": "👀 Watch Battles", "details": "Details", "none": "No Battles are available yet.",
        "no_open": "Registration is currently closed. You can still watch ongoing Battles.",
        "confirm_title": "🏆 <b>Confirm your entry</b>",
        "confirm": "✅ Confirm and pay", "back": "◀️ Back to Battles",
        "confirm_hint": "Confirm to debit your Kisa wallet. One container per participant per Battle.",
        "success": "✅ <b>You're in!</b>", "container": "Your container",
        "charged": "Charged", "balance": "Kisa left",
        "insufficient": "Not enough Kisa. Entry fee: Ⓚ {price}; your balance: Ⓚ {balance}.",
        "buy": "⭐ Add Kisa", "already": "You're already in this Battle.",
        "closed": "Registration is closed or no places are left.",
        "try_again": "Could not join the Battle. Please try again later.",
        "private": "Open a private chat with @KisaMoreBot to join.",
        "terms": "Please accept KisaMore's terms before your first purchase.",
        "accept": "📄 Review and accept terms",
        "status": "Status", "rack": "Rack", "places": "Participants",
        "entry": "Container", "view": "🌱 My plant",
        "history": "Previous Battles", "first": "Enter /battle to join.",
        "account": "Kisa wallet",
    },
}

def tr(lang: str, key: str) -> str:
    return COPY["ru" if lang == "ru" else "en"][key]

def locale(tg: dict) -> str:
    return "ru" if str(tg.get("language_code") or "").lower().startswith("ru") else "en"

def battle_key(value: str) -> str | None:
    try:
        return str(UUID(value))
    except (ValueError, TypeError):
        return None

async def _battles_and_ownership(telegram_id: int):
    async with SessionLocal() as session:
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id)
        )).scalar_one_or_none()
        wallet = (await session.execute(select(WalletAccount)
                  .where(WalletAccount.user_id == user.id))).scalar_one_or_none() if user else None
        rows = list((await session.execute(
            select(PlantBattle, Plant).join(Plant, PlantBattle.plant_id == Plant.id)
            .where(PlantBattle.status != "cancelled")
            .order_by(PlantBattle.created_at.desc()).limit(25)
        )).all())
        ids=[b.id for b,_ in rows]
        entries=list((await session.execute(
            select(PlantBattleEntry).where(
                PlantBattleEntry.battle_id.in_(ids),
                PlantBattleEntry.status.in_(("active","finished")),
            )
        )).scalars().all()) if ids else []
    counts=Counter(e.battle_id for e in entries if e.status == "active")
    mine={}
    if user:
        for entry in entries:
            if (user.marketplace_user_id and entry.user_id == user.marketplace_user_id) or (
                entry.telegram_user_id == user.id
            ):
                mine[entry.battle_id]=entry
    return rows, counts, mine, user, int(wallet.balance) if wallet else 0

def _plant(plant: Plant, lang: str) -> str:
    names=plant.names or {}
    return escape(str(names.get(lang) or names.get("en") or names.get("ru") or plant.code))

def _status(battle: PlantBattle, lang: str) -> str:
    return tr(lang, battle.status) if battle.status in COPY["en"] else escape(battle.status)

def _back(lang: str):
    return [{"text": tr(lang,"back"), "callback_data":"battle:list"}]

async def show_lobby(bot, chat_id: int, tg: dict, *, mine_only: bool=False):
    lang=locale(tg)
    rows,counts,mine,user,balance=await _battles_and_ownership(int(tg["id"]))
    text=[tr(lang,"title"),tr(lang,"intro"),
          f"\nⓀ {tr(lang,'wallet')}: <b>{balance}</b>"]
    keyboard=[]
    shown=0
    for battle,plant in rows:
        is_mine=mine.get(battle.id)
        if mine_only and not is_mine: continue
        if not mine_only and battle.status=="finished" and not is_mine: continue
        shown+=1
        left=max(0,battle.max_entries-counts[battle.id])
        text.append(
            f"\n<b>{escape(battle.title)}</b>\n"
            f"🌿 {_plant(plant,lang)} · {tr(lang,'rack')} {battle.rack_id}\n"
            f"{_status(battle,lang)} · {tr(lang,'places')}: {counts[battle.id]}/{battle.max_entries}\n"
            f"Ⓚ {tr(lang,'price')}: {battle.entry_price_kisa} · "
            f"Ⓚ {tr(lang,'prize')}: {battle.winner_reward_kisa}"
            + (f" · {tr(lang,'vacant')}: {left}" if battle.status=="open" else "")
        )
        if is_mine:
            keyboard.append([{"text":f"🌱 {battle.title[:35]} · #{is_mine.slot_number}",
                              "callback_data":open_callback(is_mine.id)}])
        elif battle.status=="open" and left:
            keyboard.append([{"text":f"{tr(lang,'join')} · {battle.title[:23]}",
                              "callback_data":f"battle:join:{battle.id}"}])
        else:
            keyboard.append([{"text":f"👀 {battle.title[:34]}",
                              "callback_data":f"battle:details:{battle.id}"}])
    if not shown:
        text.append("\n"+(tr(lang,"none") if mine_only else tr(lang,"no_open")))
    if not mine_only:
        keyboard.append([{"text":tr(lang,"mine"),"callback_data":"battle:mine"}])
    else:
        keyboard.append([{"text":tr(lang,"watch"),"callback_data":"battle:list"}])
    keyboard.append([{"text":core.t(lang,"back_home"),"callback_data":"menu:home"}])
    await bot.send_message(chat_id,"\n".join(text)[:3900],reply_markup={"inline_keyboard":keyboard})

async def show_details(bot,chat_id:int,tg:dict,battle_id:str,*,confirmation=False):
    lang=locale(tg)
    rows,counts,mine,user,balance=await _battles_and_ownership(int(tg["id"]))
    item=next(((b,p) for b,p in rows if b.id==battle_id),None)
    if not item:
        await bot.send_message(chat_id,tr(lang,"closed"),reply_markup={"inline_keyboard":[_back(lang)]})
        return
    battle,plant=item
    left=max(0,battle.max_entries-counts[battle.id])
    text=[tr(lang,"confirm_title") if confirmation else f"🏆 <b>{escape(battle.title)}</b>",
          f"\n🌿 {_plant(plant,lang)}",
          f"📷 {tr(lang,'rack')} {battle.rack_id}",
          f"{tr(lang,'status')}: {_status(battle,lang)}",
          f"{tr(lang,'places')}: {counts[battle.id]}/{battle.max_entries}",
          f"{tr(lang,'vacant')}: {left}",
          f"Ⓚ {tr(lang,'price')}: <b>{battle.entry_price_kisa}</b>",
          f"🏆 Ⓚ {tr(lang,'prize')}: {battle.winner_reward_kisa}",
          f"Ⓚ {tr(lang,'wallet')}: <b>{balance}</b>",
          "\n"+tr(lang,"confirm_hint") if confirmation else "\n"+tr(lang,"intro")]
    keyboard=[]
    own=mine.get(battle_id)
    if own:
        text.append("\n"+tr(lang,"already"))
        keyboard.append([{"text":tr(lang,"view"),"callback_data":open_callback(own.id)}])
    elif battle.status=="open" and left:
        if confirmation:
            keyboard.append([{"text":tr(lang,"confirm"),
                              "callback_data":f"battle:confirm:{battle.id}"}])
        else:
            keyboard.append([{"text":tr(lang,"join"),
                              "callback_data":f"battle:join:{battle.id}"}])
    keyboard.append(_back(lang))
    await bot.send_message(chat_id,"\n".join(text),reply_markup={"inline_keyboard":keyboard})

async def join(bot,chat_id:int,tg:dict,battle_id:str):
    lang=locale(tg)
    # Native Telegram users have a technical, inactive website identity,
    # as with Telegram-first rentals. Account linking later migrates entries.
    user,_=await core.get_or_create_user(tg)
    if not user.is_active:
        await bot.send_message(chat_id,tr(lang,"try_again"))
        return
    if not user.terms_accepted_at:
        await bot.send_message(chat_id,tr(lang,"terms"),reply_markup={
            "inline_keyboard":[
                [{"text":tr(lang,"accept"),"callback_data":"terms:show"}],
                _back(lang)
            ]})
        return

    try:
        async with SessionLocal() as session:
            tg_user=(await session.execute(
                select(TelegramUser).where(TelegramUser.id==user.id)
            )).scalar_one()
            web_user=await _ensure_marketplace_user(session,tg_user)
            # Shared transaction; this is EXACTLY the website purchase path.
            receipt=await join_battle(
                battle_id,JoinBattleIn(quantity=1),user=web_user,session=session
            )
    except HTTPException as e:
        if e.status_code in (404,409):
            detail=str(e.detail)
            if "already" in detail.lower():
                await bot.send_message(chat_id,tr(lang,"already"))
            elif "not enough" in detail.lower():
                rows,_,_,_,bal=await _battles_and_ownership(int(tg["id"]))
                current=next((b for b,_ in rows if b.id==battle_id),None)
                price=current.entry_price_kisa if current is not None else "—"
                await bot.send_message(
                    chat_id,tr(lang,"insufficient").format(price=price,balance=bal),
                    reply_markup={"inline_keyboard":[
                        [{"text":tr(lang,"buy"),"callback_data":"menu:wallet"}],_back(lang)]
                    })
            else:
                await bot.send_message(chat_id,tr(lang,"closed"))
        else:
            core.logger.exception("Battle Telegram join rejected: %s",e)
            await bot.send_message(chat_id,tr(lang,"try_again"))
        return
    except Exception:
        core.logger.exception("Telegram Battle purchase failed")
        await bot.send_message(chat_id,tr(lang,"try_again"))
        return
    text=(tr(lang,"success")+
          f"\n{tr(lang,'container')}: <b>#{receipt['slots'][0]}</b>"
          f"\n{tr(lang,'charged')}: Ⓚ {receipt['charged_kisa']}"
          f"\n{tr(lang,'balance')}: Ⓚ {receipt['balance']}")
    await bot.send_message(chat_id,text,reply_markup={"inline_keyboard":[
        [{"text":tr(lang,"view"),"callback_data":open_callback(receipt["entry_ids"][0])}],
        _back(lang)
    ]})

def install(core_module) -> None:
    if getattr(core_module,"_battle_lobby_installed",False):return
    previous_message=core_module.handle_message
    previous_callback=core_module.handle_callback
    previous_keyboard=core_module.main_keyboard

    def main_keyboard(lang):
        data=previous_keyboard(lang)
        rows=list(data["inline_keyboard"])
        rows.insert(-1,[{"text":"🏆 Битвы растений" if lang=="ru" else "🏆 Plant Battles",
                         "callback_data":"battle:list"}])
        return {"inline_keyboard":rows}

    async def handle_message(bot,message):
        text=str(message.get("text") or "").strip()
        command=text.split(maxsplit=1)[0].split("@",1)[0].lower()
        if command != "/battle":
            await previous_message(bot,message)
            return
        tg=message.get("from") or {}
        chat_id=(message.get("chat") or {}).get("id")
        if not tg.get("id") or chat_id is None:return
        if int(chat_id)!=int(tg["id"]):
            await bot.send_message(chat_id,tr(locale(tg),"private"))
            return
        await core_module.get_or_create_user(tg)
        await show_lobby(bot,chat_id,tg)

    async def handle_callback(bot,query):
        data=str(query.get("data") or "")
        if data not in ("battle:list","battle:mine","menu:battle") and not any(
            data.startswith(p) for p in ("battle:join:","battle:confirm:","battle:details:")
        ):
            await previous_callback(bot,query)
            return
        tg=query.get("from") or {}
        chat_id=((query.get("message") or {}).get("chat") or {}).get("id")
        qid=query.get("id")
        if not tg.get("id") or chat_id is None or not qid:return
        if int(chat_id)!=int(tg["id"]):
            await bot.answer_callback_query(qid,text=tr(locale(tg),"private"),show_alert=True)
            return
        await bot.answer_callback_query(qid)
        try:
            if data in ("battle:list","menu:battle"):
                await show_lobby(bot,chat_id,tg)
            elif data=="battle:mine":
                await show_lobby(bot,chat_id,tg,mine_only=True)
            else:
                prefix,_,battle_id=data.rpartition(":")
                battle_id=battle_key(battle_id)
                if not battle_id:
                    await bot.send_message(chat_id,tr(locale(tg),"closed"))
                elif prefix=="battle:join":
                    await show_details(bot,chat_id,tg,battle_id,confirmation=True)
                elif prefix=="battle:confirm":
                    await join(bot,chat_id,tg,battle_id)
                else:
                    await show_details(bot,chat_id,tg,battle_id)
        except Exception:
            core_module.logger.exception("Telegram /battle interaction failed")
            await bot.send_message(chat_id,tr(locale(tg),"try_again"))

    core_module.main_keyboard=main_keyboard
    core_module.handle_message=handle_message
    core_module.handle_callback=handle_callback
    core_module._battle_lobby_installed=True
