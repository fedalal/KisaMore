
"""Regression tests: Battle morning button stays in Telegram and enforces ownership."""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import patch

from PIL import Image

from cloud.app.telegram import battle_player
from cloud.app.telegram.battle_notifications import discover_battle_daily_updates

ENTRY = "af47235b-5cc0-441a-bfc6-e5f1dd640289"
BATTLE = "27195efe-6f1a-488e-bf38-3648fb582e81"
USER = "web-user-1"


class Rows:
    def __init__(self, rows=None, scalar=None):
        self.rows = rows or []
        self.scalar = scalar

    def scalar_one_or_none(self):
        return self.scalar

    def one_or_none(self):
        return self.rows[0] if self.rows else None

    def scalars(self):
        return self

    def all(self):
        return self.rows


class Session:
    def __init__(self, telegram_user, entry, battle, plant, photos, calibration=None, actions=None):
        self.answers = [
            Rows(scalar=telegram_user),
            Rows(rows=[(entry, battle, plant)]),
            Rows(rows=photos),
            Rows(scalar=calibration),
            Rows(rows=actions or []),
        ]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def execute(self, sql):
        return self.answers.pop(0)


class Bot:
    def __init__(self):
        self.answered = []
        self.messages = []
        self.photos = []
        self.videos = []

    async def answer_callback_query(self, query_id, **kwargs):
        self.answered.append((query_id, kwargs))

    async def send_message(self, chat_id, text, *, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))

    async def send_photo(self, chat_id, path, *, caption="", reply_markup=None):
        self.photos.append((chat_id, str(path), caption, reply_markup))

    async def send_video(self, chat_id, path, *, caption="", reply_markup=None):
        self.videos.append((chat_id, str(path), caption, reply_markup))


def query(data, telegram_id=111):
    return {"id":"callback_1", "data":data, "from":{"id":telegram_id,"language_code":"ru"},
            "message":{"chat":{"id":telegram_id}, "message_id":7}}


def context(photo_dir, linked_user=USER, telegram_entry_id=None, has_photo=True):
    tg=NS(telegram_user_id=111, is_active=True, marketplace_user_id=linked_user, id=12)
    entry=NS(id=ENTRY, battle_id=BATTLE, user_id=USER, telegram_user_id=telegram_entry_id,
             status="active", slot_number=1, water_used_ml=150, nutrient_used_ml=0,
             shade_used_minutes=30)
    battle=NS(id=BATTLE, device_id="device01", rack_id=1,
              title="Plant Battle", water_budget_ml=1000, nutrient_budget_ml=100,
              shade_budget_minutes=2000,
              planted_at=datetime(2026,10,12,10,53,tzinfo=timezone.utc))
    plant=NS(names={"ru":"Редис Ред коралл","en":"Radish"},code="radish")
    if has_photo:
        src=photo_dir/"shelf.jpg"
        Image.new("RGB",(800,500),"white").save(src)
        photos=[NS(camera_id="camera_1", is_primary=True, file_path=str(src),
                   captured_at=datetime(2026,10,13,7,0,tzinfo=timezone.utc))]
    else:
        photos=[]
    cal=NS(slot_outlines={"1":[[.1,.1],[.45,.1],[.45,.4],[.1,.4]]})
    actions=[NS(kind="water",amount=150,status="completed")]
    return Session(tg,entry,battle,plant,photos,cal,actions)


async def main():
    import logging
    from cloud.app.telegram import bot as telegram_transport
    assert logging.getLogger("httpx").level >= logging.WARNING, "Do not log URLs with bot secrets"
    assert "url" not in {"callback_data":battle_player.open_callback(ENTRY)}
    assert len(battle_player.video_callback(ENTRY,"full","camera_5").encode()) <= 64

    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        b=Bot()
        with patch.object(battle_player,"SessionLocal",new=lambda:context(root)):
            assert await battle_player.handle_callback(b,query(battle_player.open_callback(ENTRY)))
        assert len(b.answered)==1 and len(b.photos)==1
        assert not b.messages
        chat_id,path,caption,keyboard=b.photos[0]
        assert chat_id==111
        assert "Редис Ред коралл" in caption
        assert "850 мл" in caption and "1970 мин" in caption
        assert path.endswith(".jpg")
        assert not Path(path).exists(), "Temporary highlighted photo cleaned up"
        keys=[button["callback_data"] for row in keyboard["inline_keyboard"] for button in row]
        assert battle_player.open_callback(ENTRY) in keys
        assert battle_player.video_callback(ENTRY,"24h","camera_1") in keys
        assert not any("url" in button for row in keyboard["inline_keyboard"] for button in row)

        b=Bot()
        with patch.object(battle_player,"SessionLocal",new=lambda:context(root,linked_user="someone-else")):
            assert await battle_player.handle_callback(b,query(battle_player.open_callback(ENTRY)))
        assert not b.photos and b.messages
        assert "недоступно" in b.messages[0][1]
        assert len(b.answered)==1

        b=Bot()
        with patch.object(battle_player,"SessionLocal",new=lambda:context(root,has_photo=False)):
            await battle_player.handle_callback(b,query(battle_player.open_callback(ENTRY)))
        assert not b.photos and len(b.messages)==1
        assert "850 мл" in b.messages[0][1]

        b=Bot()
        with patch.object(battle_player,"SessionLocal",new=lambda:context(root)):
            await battle_player.handle_callback(b,query(battle_player.video_callback(ENTRY,"24h","camera_1")))
        assert not b.videos and len(b.messages)==1 and "пока не готов" in b.messages[0][1]

        video=root/"timelapse"/"battles"/BATTLE/"camera_1"/"24h.mp4"
        video.parent.mkdir(parents=True)
        video.write_bytes(b"dummy-video")
        b=Bot()
        with patch.object(battle_player,"SessionLocal",new=lambda:context(root)), \
             patch.object(battle_player,"get_settings",new=lambda:NS(photo_dir=root)):
            await battle_player.handle_callback(b,query(battle_player.video_callback(ENTRY,"24h","camera_1")))
        assert len(b.videos)==1 and b.videos[0][1]==str(video)

        b=Bot()
        with patch.object(battle_player,"SessionLocal",new=lambda:context(root,linked_user="different")):
            await battle_player.handle_callback(b,query(battle_player.video_callback(ENTRY,"24h","camera_1")))
        assert not b.videos

        b=Bot()
        with patch.object(battle_player,"SessionLocal",new=lambda:context(root)):
            await battle_player.handle_callback(b,query(battle_player.video_callback(ENTRY,"24h","camera_5")))
        assert not b.videos, "Cannot select another camera not attached to this Battle"

        b=Bot()
        with patch.object(battle_player,"SessionLocal",new=lambda:context(root)):
            await battle_player.handle_callback(b,query("battle:open:not-a-uuid"))
        assert not b.photos and b.answered[-1][1].get("show_alert") is True

        b=Bot()
        forwarded=query(battle_player.open_callback(ENTRY))
        forwarded["message"]["chat"]["id"]=-100500
        assert await battle_player.handle_callback(b,forwarded)
        assert b.answered[-1][1].get("show_alert") is True
        assert not b.messages and not b.photos, "Private resources must not be sent to groups"

        b=Bot()
        assert not await battle_player.handle_callback(b,query("menu:home"))
        assert not b.answered
    print("PASS: Telegram-only Battle card, full rack photo, live resources, ownership, timelapse, invalid callbacks")


if __name__=="__main__":
    asyncio.run(main())
