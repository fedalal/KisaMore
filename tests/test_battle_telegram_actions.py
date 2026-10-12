import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

from cloud.app import battle_admin_api
from cloud.app.battle_service import BATTLE_MESSAGES, queue_telegram_text
from cloud.app.telegram import worker_admin


class Session:
    def __init__(self):
        self.rows = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, *args):
        return None

    def add(self, item):
        self.rows.append(item)


class Bot:
    def __init__(self):
        self.answers = []
        self.messages = []
        self.calls = []

    async def answer_callback_query(self, *args, **kwargs):
        self.answers.append((args, kwargs))

    async def send_message(self, *args, **kwargs):
        self.messages.append((args, kwargs))

    async def call(self, *args, **kwargs):
        self.calls.append((args, kwargs))


ID = "02e80387-c2d2-46cf-92e8-cf77cf2d183f"


def update(operation):
    return {
        "id": "callback-id",
        "data": f"adminbattle:{operation}:{ID}",
        "from": {"id": 999, "first_name": "Admin"},
        "message": {"message_id": 71, "chat": {"id": 999}},
    }


async def main():
    assert "\n" in BATTLE_MESSAGES["ru"]["action_rejected"]

    session = Session()
    markup = worker_admin._battle_action_keyboard(ID)
    assert all(len(button["callback_data"].encode("utf-8")) <= 64 for row in markup["inline_keyboard"] for button in row)
    await queue_telegram_text(
        session, telegram_user_id=999, event_key="test-battle-action",
        text="Test", reply_markup=markup,
    )
    assert session.rows[0].payload["reply_markup"] == markup

    with patch.object(worker_admin, "_authorized_admin", new=AsyncMock(return_value=(None, object()))), \
         patch.object(worker_admin, "SessionLocal", new=lambda: Session()), \
         patch.object(battle_admin_api, "complete_action", new=AsyncMock(return_value={"ok": True, "status": "completed"})) as complete, \
         patch.object(battle_admin_api, "reject_action", new=AsyncMock(return_value={"ok": True, "status": "rejected"})) as reject:
        bot = Bot()
        assert await worker_admin._handle_admin_battle_callback(bot, update("done"))
        assert complete.await_count == 1
        assert bot.calls[0][0][0] == "editMessageReplyMarkup"
        assert "✅" in bot.messages[0][0][1]

        bot = Bot()
        await worker_admin._handle_admin_battle_callback(bot, update("reject"))
        assert reject.await_count == 0
        assert bot.messages[0][1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == f"adminbattle:rejectconfirm:{ID}"

        bot = Bot()
        await worker_admin._handle_admin_battle_callback(bot, update("rejectconfirm"))
        assert reject.await_count == 1
        assert "❌" in bot.messages[0][0][1]

        complete.side_effect = HTTPException(status_code=409, detail="Already handled")
        bot = Bot()
        await worker_admin._handle_admin_battle_callback(bot, update("done"))
        assert bot.answers[0][1].get("show_alert") is True
        assert not bot.calls

    with patch.object(worker_admin, "_authorized_admin", new=AsyncMock(return_value=(None, None))):
        bot = Bot()
        await worker_admin._handle_admin_battle_callback(bot, update("done"))
        assert bot.answers[0][1].get("show_alert") is True

    print("PASS: queue markup; complete; reject confirmation; reject; stale; admin authorization")


if __name__ == "__main__":
    asyncio.run(main())
