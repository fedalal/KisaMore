from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base

class BattleAdminMessage(Base):
    __tablename__="battle_admin_messages"
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    battle_id: Mapped[str]=mapped_column(ForeignKey("plant_battles.id"),index=True,nullable=False)
    author_user_id: Mapped[str]=mapped_column(ForeignKey("users.id"),nullable=False)
    body: Mapped[str]=mapped_column(Text,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)


class BattleMessageReceipt(Base):
    __tablename__="battle_message_receipts"
    __table_args__=(Index("uq_battle_message_recipient","message_id","entry_id",unique=True),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    message_id: Mapped[str]=mapped_column(ForeignKey("battle_admin_messages.id"),index=True,nullable=False)
    entry_id: Mapped[str]=mapped_column(ForeignKey("plant_battle_entries.id"),index=True,nullable=False)
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True,nullable=False)
    read_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
