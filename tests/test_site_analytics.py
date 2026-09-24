import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock

os.environ.setdefault('KISAMORE_DATABASE_URL', f'sqlite+aiosqlite:///{Path(tempfile.mkdtemp()) / "analytics.db"}')
os.environ['KISAMORE_COOKIE_SECURE'] = 'false'

from fastapi.testclient import TestClient
from sqlalchemy import select
from cloud.app.main import app
from cloud.app.db import SessionLocal, create_tables
from cloud.app.models import User
from cloud.app.security import hash_password
from cloud.app.site_analytics_models import PageView, SiteRegistration, SiteRegistrationDelivery
from cloud.app.telegram.admin_models import TelegramAdmin
from cloud.app.telegram.models import TelegramUser
from cloud.app.telegram.site_registration_notifier import send_pending_alerts


def test_tracking_registration_and_durable_notifications():
    marker = str(uuid4())
    email = f'{marker}@example.com'
    admin_email = f'admin-{marker}@example.com'

    async def setup():
        await create_tables()
        async with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            tg = TelegramUser(telegram_user_id=int(uuid4().int % 10**12), first_name='Admin', language_code='ru', is_active=True)
            db.add(tg)
            db.add(User(id=str(uuid4()), email=admin_email, display_name='Admin',
                        password_hash=hash_password('test-password-123'), role='admin', created_at=now))
            await db.flush()
            db.add(TelegramAdmin(user_id=tg.id, enabled=True))
            await db.commit()
            return tg.id

    admin_id = asyncio.run(setup())
    with TestClient(app) as client:
        assert client.get('/api/v1/admin/analytics').status_code == 401
        payload = dict(event_id=str(uuid4()), path='/', source='telegram', medium='paid', campaign=marker, utm_content='cvety_uhod')
        assert client.post('/api/v1/analytics/visit', json=payload).status_code == 204
        assert client.cookies.get('kisamore_visitor')
        assert client.post('/api/v1/analytics/visit', json=payload).status_code == 204
        client.get('/api/v1/health')  # Polling must not create another page view.
        assert client.post('/api/v1/analytics/visit', json={**payload, 'event_id': str(uuid4())}, headers={'User-Agent': 'Googlebot'}).status_code == 204
        assert client.post('/api/v1/analytics/visit', json={**payload, 'event_id': str(uuid4())}, headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
        assert client.post('/api/v1/analytics/visit', json={**payload, 'path': '/?reset_token=secret'}).status_code == 422
        # A second opening is a view, but remains the same visitor and visit.
        assert client.post('/api/v1/analytics/visit', json=dict(event_id=str(uuid4()), path='/')).status_code == 204
        registered = client.post('/api/v1/auth/register', json=dict(email=email, display_name='<Alex>', password='test-password-123', language='en'))
        assert registered.status_code == 201, registered.text
        user_id = registered.json()['id']
        assert client.get('/api/v1/admin/analytics').status_code == 403
        assert client.post('/api/v1/auth/register', json=dict(email=email, display_name='Alex', password='test-password-123', language='en')).status_code == 409
        assert client.post('/api/v1/auth/login', json=dict(email=email, password='test-password-123')).status_code == 200
        assert client.post('/api/v1/auth/login', json=dict(email=admin_email, password='test-password-123')).status_code == 200
        data = client.get('/api/v1/admin/analytics?days=7').json()
        source = next(s for s in data['sources'] if s['campaign'] == marker)
        assert (source['views'], source['visitors'], source['visits'], source['registrations']) == (2, 1, 1, 1)
        assert source['utm_content'] == 'cvety_uhod'
        assert client.get('/api/v1/admin/analytics?days=0').status_code == 422

    async def verify():
        async with SessionLocal() as db:
            registration = await db.get(SiteRegistration, user_id)
            assert registration.campaign == marker
            assert registration.utm_content == 'cvety_uhod'
            deliveries = (await db.execute(select(SiteRegistrationDelivery).where(
                SiteRegistrationDelivery.user_id == user_id, SiteRegistrationDelivery.admin_user_id == admin_id))).scalars().all()
            assert len(deliveries) == 1
        bot = AsyncMock()
        bot.send_message.side_effect = RuntimeError('temporary outage')
        await send_pending_alerts(bot)
        async with SessionLocal() as db:
            delivery = (await db.execute(select(SiteRegistrationDelivery).where(
                SiteRegistrationDelivery.user_id == user_id, SiteRegistrationDelivery.admin_user_id == admin_id))).scalar_one()
            assert delivery.sent_at is None and delivery.attempts == 1
            delivery.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await db.commit()
        bot.send_message.side_effect = None
        await send_pending_alerts(bot)
        assert any('&lt;Alex&gt;' in call.args[1] and marker in call.args[1] and 'cvety_uhod' in call.args[1] for call in bot.send_message.call_args_list)
        bot.reset_mock()
        await send_pending_alerts(bot)
        bot.send_message.assert_not_called()
        # An opening after 30 minutes starts a new visit without a new visitor.
        async with SessionLocal() as db:
            rows = (await db.execute(select(PageView).where(PageView.campaign == marker))).scalars().all()
            for row in rows:
                row.created_at = datetime.now(timezone.utc) - timedelta(minutes=31)
            await db.commit()
        return registration.visitor_id

    visitor = asyncio.run(verify())
    with TestClient(app) as client:
        client.cookies.set('kisamore_visitor', visitor)
        client.post('/api/v1/analytics/visit', json=dict(event_id=str(uuid4()), path='/', source='telegram', medium='paid', campaign=marker, utm_content='cvety_uhod'))
        client.post('/api/v1/auth/login', json=dict(email=admin_email, password='test-password-123'))
        source = next(s for s in client.get('/api/v1/admin/analytics?days=7').json()['sources'] if s['campaign'] == marker)
        assert (source['views'], source['visitors'], source['visits']) == (3, 1, 2)


def test_utm_content_separates_placements():
    marker = str(uuid4())
    for content in ('cvety_uhod', 'another_channel'):
        with TestClient(app) as client:
            assert client.post('/api/v1/analytics/visit', json=dict(
                event_id=str(uuid4()), source='telegain', medium='cpp', campaign=marker,
                utm_content=content)).status_code == 204
    from cloud.app.site_analytics import analytics
    async def check():
        async with SessionLocal() as db:
            result = await analytics(days=7, _=None, session=db)
            rows = [row for row in result['sources'] if row['campaign'] == marker]
            assert {row['utm_content'] for row in rows} == {'cvety_uhod', 'another_channel'}
            assert all(row['views'] == 1 and row['visitors'] == 1 for row in rows)
    asyncio.run(check())


def test_existing_analytics_schema_migrates_without_data_loss():
    from sqlalchemy import create_engine, inspect
    from cloud.app.db import _ensure_analytics_columns
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        for table in ('site_pageviews', 'site_registrations'):
            connection.exec_driver_sql(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, campaign VARCHAR(100))')
            connection.exec_driver_sql(f"INSERT INTO {table} (id, campaign) VALUES (1, 'existing')")
        _ensure_analytics_columns(connection)
        _ensure_analytics_columns(connection)
        for table in ('site_pageviews', 'site_registrations'):
            assert connection.exec_driver_sql(f'SELECT campaign, utm_content FROM {table}').one() == ('existing', '')
            column = next(c for c in inspect(connection).get_columns(table) if c['name'] == 'utm_content')
            assert column['nullable'] is False
    engine.dispose()
