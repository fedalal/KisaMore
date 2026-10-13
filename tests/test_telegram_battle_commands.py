"""Commands and handlers always expose /battle in Telegram."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import patch

from cloud.app.telegram import worker_daily_photos as w
from cloud.app.telegram.bot import _commands_for
from cloud.app.telegram.profile_locales import BOT_PROFILE_LOCALIZATIONS
from cloud.app.telegram import battle_lobby

async def main():
    assert getattr(w.core,"_battle_lobby_installed",False)
    for lang,locale in BOT_PROFILE_LOCALIZATIONS.items():
        commands=_commands_for(lang,locale)
        assert sum(c["command"]=="battle" for c in commands)==1
        markup=w.core.main_keyboard(lang)
        assert sum(b.get("callback_data")=="battle:list" for row in markup["inline_keyboard"] for b in row)==1
        rows = markup["inline_keyboard"]
        profile_language = [
            row for row in rows
            if any(b.get("callback_data") == "menu:profile" for b in row)
        ]
        assert len(profile_language) == 1, f"Profile row missing for {lang}"
        assert [b["callback_data"] for b in profile_language[0]] == [
            "menu:profile", "lang:menu"
        ], f"Profile and Language must share one row for {lang}"
        assert sum(
            b.get("callback_data") == "lang:menu"
            for row in rows for b in row
        ) == 1, f"Duplicate Language button for {lang}"
        assert len(rows[0]) == 2 and len(rows[1]) == 2, (
            f"Existing two-column top rows changed for {lang}"
        )
    events=[]
    class Bot:
        async def send_message(self,*args,**kwargs):
            events.append(("message",args,kwargs))
        async def answer_callback_query(self,*args,**kwargs):
            events.append(("ack",args,kwargs))
    bot=Bot()
    async def fake_lobby(bot,chat,tg,**kw):
        events.append(("battle_lobby",chat,tg,kw))
    async def fake_get_user(tg):
        return NS(),NS()
    with patch.object(battle_lobby,"show_lobby",new=fake_lobby),\
         patch.object(w.core,"get_or_create_user",new=fake_get_user):
        await w.core.handle_message(bot,{"text":"/battle","from":{"id":71,"language_code":"ru"},
                                          "chat":{"id":71,"type":"private"}})
        assert any(e[0]=="battle_lobby" for e in events)
        events.clear()
        await w.core.handle_message(bot,{"text":"/battle","from":{"id":71,"language_code":"ru"},
                                          "chat":{"id":-200,"type":"supergroup"}})
        assert all(e[0]!="battle_lobby" for e in events)
        assert any("личный чат" in e[1][1] for e in events if e[0]=="message")
        events.clear()
        await w.core.handle_callback(bot,{
            "data":"battle:list","id":"qid",
            "from":{"id":71,"language_code":"ru"},
            "message":{"chat":{"id":71,"type":"private"}}
        })
        assert any(e[0]=="ack" for e in events) and any(e[0]=="battle_lobby" for e in events)
        events.clear()
        await w.core.handle_callback(bot,{
            "data":"battle:confirm:invalid","id":"qid",
            "from":{"id":71,"language_code":"ru"},
            "message":{"chat":{"id":71,"type":"private"}}
        })
        assert any(e[0]=="ack" for e in events)
        assert any("Запись закрыта" in e[1][1] for e in events if e[0]=="message")
    print("PASS: two-column Profile + Language menu in 9 languages, /battle, private chat and invalid callbacks.")

if __name__=="__main__":
    asyncio.run(main())
