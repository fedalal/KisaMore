from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import User
from .security import get_admin_user, get_session
from .site_analytics_models import PageView, SiteRegistration, SiteRegistrationDelivery
from .telegram.admin_models import TelegramAdmin

router = APIRouter(tags=['site analytics'])
VISITOR_COOKIE = 'kisamore_visitor'


def visitor_cookie(request):
    try:
        return str(UUID(request.cookies.get(VISITOR_COOKIE, '')))
    except (ValueError, TypeError):
        return None


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class VisitIn(BaseModel):
    event_id: UUID
    path: str = Field(default='/', max_length=255, pattern=r'^/[^?#]*$')
    source: str = Field(default='', max_length=100)
    medium: str = Field(default='', max_length=100)
    campaign: str = Field(default='', max_length=100)
    referrer: str = Field(default='', max_length=2048)


@router.post('/api/v1/analytics/visit', status_code=204)
async def visit(payload: VisitIn, request: Request, response: Response,
                session: AsyncSession = Depends(get_session)):
    # Do not accept third-party browser submissions or count known crawlers.
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'Same-origin requests only')
    agent = request.headers.get('user-agent', '').lower()
    if any(word in agent for word in ('bot', 'crawler', 'spider', 'headless')):
        return
    if payload.path != '/':
        raise HTTPException(422, 'Only the public dashboard is tracked')
    visitor = visitor_cookie(request) or str(uuid4())
    response.set_cookie(VISITOR_COOKIE, visitor, max_age=365 * 86400,
                        secure=get_settings().cookie_secure, httponly=True, samesite='lax')
    if await session.get(PageView, str(payload.event_id)):
        return
    now = datetime.now(timezone.utc)
    last = (await session.execute(select(PageView).where(PageView.visitor_id == visitor)
                                  .order_by(PageView.created_at.desc()).limit(1))).scalar_one_or_none()
    continued = last is not None and aware(last.created_at) > now - timedelta(minutes=30)
    try:
        referrer_host = urlsplit(payload.referrer).hostname or ''
    except ValueError:
        referrer_host = ''
    external = referrer_host and referrer_host != request.url.hostname
    source = payload.source.strip() or (referrer_host[:100] if external else 'direct')
    medium = payload.medium.strip() or ('referral' if external else '')
    campaign = payload.campaign.strip()
    # Preserve the entry source across reloads during the same visit.
    if continued:
        source, medium, campaign = last.source, last.medium, last.campaign
    session.add(PageView(id=str(payload.event_id), visitor_id=visitor,
                         session_id=last.session_id if continued else str(uuid4()),
                         path=payload.path, source=source, medium=medium,
                         campaign=campaign, created_at=now))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()  # Concurrent retries of the same page event.


async def record_registration(session, user, request):
    """Called within the registration transaction; login never calls this."""
    visitor = visitor_cookie(request)
    last = (await session.execute(select(PageView).where(PageView.visitor_id == visitor)
                                  .order_by(PageView.created_at.desc()).limit(1))).scalar_one_or_none() if visitor else None
    row = SiteRegistration(user_id=user.id, visitor_id=visitor,
                           source=last.source if last else 'unknown',
                           medium=last.medium if last else '',
                           campaign=last.campaign if last else '', created_at=user.created_at)
    session.add(row)
    await session.flush()
    admins = (await session.execute(select(TelegramAdmin.user_id).where(TelegramAdmin.enabled.is_(True)))).scalars()
    for admin_id in admins:
        session.add(SiteRegistrationDelivery(user_id=user.id, admin_user_id=admin_id,
                                             next_attempt_at=user.created_at))


@router.get('/api/v1/admin/analytics')
async def analytics(days: int = Query(default=7, ge=1, le=366),
                    _: User = Depends(get_admin_user), session: AsyncSession = Depends(get_session)):
    tz = ZoneInfo(get_settings().farm_timezone)
    now = datetime.now(timezone.utc)
    start = (now.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
             - timedelta(days=days - 1)).astimezone(timezone.utc)
    period = (PageView.created_at >= start, PageView.created_at <= now)
    views, visitors, visits = (await session.execute(select(func.count(PageView.id),
        func.count(func.distinct(PageView.visitor_id)), func.count(func.distinct(PageView.session_id))).where(*period))).one()
    registrations = (await session.execute(select(func.count(SiteRegistration.user_id)).where(
        SiteRegistration.created_at >= start, SiteRegistration.created_at <= now))).scalar_one()
    converted = (await session.execute(select(func.count(func.distinct(SiteRegistration.visitor_id))).where(
        SiteRegistration.created_at >= start, SiteRegistration.created_at <= now,
        SiteRegistration.visitor_id.in_(select(PageView.visitor_id).where(*period))))).scalar_one()
    sources = (await session.execute(select(PageView.source, PageView.medium, PageView.campaign,
        func.count(PageView.id), func.count(func.distinct(PageView.visitor_id)),
        func.count(func.distinct(PageView.session_id))).where(*period)
        .group_by(PageView.source, PageView.medium, PageView.campaign)
        .order_by(func.count(PageView.id).desc()).limit(100))).all()
    registered_sources = dict(((s, m, c), n) for s, m, c, n in (await session.execute(
        select(SiteRegistration.source, SiteRegistration.medium, SiteRegistration.campaign,
               func.count(SiteRegistration.user_id)).where(SiteRegistration.created_at >= start,
               SiteRegistration.created_at <= now).group_by(SiteRegistration.source,
               SiteRegistration.medium, SiteRegistration.campaign))).all())
    return dict(days=days, timezone=str(tz), start=start, end=now, views=views,
                visitors=visitors, visits=visits, registrations=registrations,
                conversion=round(converted / visitors * 100, 2) if visitors else 0,
                sources=[dict(source=s, medium=m, campaign=c, views=p, visitors=u, visits=v,
                              registrations=registered_sources.get((s, m, c), 0))
                         for s, m, c, p, u, v in sources])
