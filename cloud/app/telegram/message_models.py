from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TelegramOutboundMessage(Base):
    """Every successfully sent Telegram message from KisaMore.

    telegram_user_id stores Telegram's numeric chat/user id rather than the
    internal telegram_users.id. This lets the low-level bot transport record
    every outgoing message without having to resolve an application user first.
    """

    __tablename__ = "telegram_outbound_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    message_type: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )
