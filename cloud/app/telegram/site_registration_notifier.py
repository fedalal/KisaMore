from datetime import datetime, timedelta, timezone
from html import escape
from sqlalchemy import func, select
from ..db import SessionLocal
from ..models import User
from ..site_analytics_models import SiteRegistration, SiteRegistrationDelivery
from .admin_models import TelegramAdmin
from .models import TelegramUser


async def send_pending_alerts(bot):
    """Use the existing admin recipients and bot; persist retries across restarts."""
    sent = failed = 0
    async with SessionLocal() as session:
        now = datetime.now(timezone.utc)
        rows = (await session.execute(select(SiteRegistrationDelivery, SiteRegistration, User, TelegramUser)
            .join(SiteRegistration, SiteRegistration.user_id == SiteRegistrationDelivery.user_id)
            .join(User, User.id == SiteRegistration.user_id)
            .join(TelegramAdmin, TelegramAdmin.user_id == SiteRegistrationDelivery.admin_user_id)
            .join(TelegramUser, TelegramUser.id == TelegramAdmin.user_id)
            .where(SiteRegistrationDelivery.sent_at.is_(None),
                   SiteRegistrationDelivery.next_attempt_at <= now,
                   TelegramAdmin.enabled.is_(True), TelegramUser.is_active.is_(True))
            .order_by(SiteRegistrationDelivery.next_attempt_at).limit(50)
            .with_for_update(skip_locked=True, of=SiteRegistrationDelivery))).all()
        total = (await session.execute(select(func.count(User.id)))).scalar_one() if rows else 0
        for delivery, registration, user, admin in rows:
            text = ('🌱 <b>Новая регистрация на сайте KisaMore</b>\n\n'
                    f'Имя: <b>{escape(user.display_name)}</b>\n'
                    f'Email: {escape(user.email)}\n'
                    'Способ: сайт (email)\n'
                    f'Источник: {escape(registration.source)}\n'
                    f'Канал: {escape(registration.medium or "—")}\n'
                    f'Кампания: {escape(registration.campaign or "—")}\n'
                    f'Размещение: {escape(registration.utm_content or "—")}\n'
                    f'Дата (UTC): {registration.created_at:%Y-%m-%d %H:%M}\n'
                    f'Всего аккаунтов сайта: {total}')
            try:
                await bot.send_message(int(admin.telegram_user_id), text)
            except Exception as exc:
                delivery.attempts += 1
                # Keep retrying, at most once per hour after repeated failures.
                delivery.next_attempt_at = now + timedelta(seconds=min(3600, 10 * 2 ** min(delivery.attempts, 9)))
                delivery.last_error = type(exc).__name__
                failed += 1
            else:
                delivery.sent_at = datetime.now(timezone.utc)
                delivery.last_error = None
                sent += 1
        await session.commit()
    return sent, failed
