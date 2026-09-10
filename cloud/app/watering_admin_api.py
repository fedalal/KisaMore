from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .admin_models import AdminAuditLog
from .models import Allocation, Plant, Planting, User, WateringTask
from .security import get_admin_user, get_session
from .watering_service import aware_utc, farm_zone, refresh_watering_tasks


router = APIRouter(prefix="/api/v1/admin/watering", tags=["admin-watering"])


class CompleteWateringIn(BaseModel):
    actual_ml: int | None = Field(default=None, ge=1, le=5000)


class SkipWateringIn(BaseModel):
    reason: str = Field(default="", max_length=500)


def _plant_name(plant: Plant) -> str:
    names = plant.names or {}
    for key in ("ru", "en"):
        if names.get(key):
            return str(names[key])
    return next((str(value) for value in names.values() if value), plant.code)


def _day_bounds(day_text: str | None) -> tuple[date, datetime, datetime]:
    zone = farm_zone()
    if day_text:
        try:
            selected = date.fromisoformat(day_text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid date") from exc
    else:
        selected = datetime.now(timezone.utc).astimezone(zone).date()
    local_start = datetime.combine(selected, time.min, tzinfo=zone)
    local_end = local_start + timedelta(days=1)
    return selected, local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


@router.get("")
async def list_watering_tasks(
    day: str | None = Query(default=None),
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    now = datetime.now(timezone.utc)
    await refresh_watering_tasks(session, now=now)
    await session.commit()

    selected, start, end = _day_bounds(day)
    rows = (
        await session.execute(
            select(WateringTask, Planting, Plant, Allocation)
            .join(Planting, Planting.id == WateringTask.planting_id)
            .join(Plant, Plant.id == Planting.plant_id)
            .outerjoin(Allocation, Allocation.id == WateringTask.allocation_id)
            .where(
                or_(
                    (WateringTask.scheduled_at >= start) & (WateringTask.scheduled_at < end),
                    (WateringTask.status == "pending") & (WateringTask.scheduled_at < start),
                )
            )
            .order_by(WateringTask.scheduled_at, WateringTask.rack_id, WateringTask.slot_number)
            .limit(1000)
        )
    ).all()

    zone = farm_zone()
    tasks = []
    overdue = pending = done = skipped = 0
    for task, planting, plant, allocation in rows:
        scheduled = aware_utc(task.scheduled_at)
        completed = aware_utc(task.completed_at)
        is_overdue = bool(task.status == "pending" and scheduled and scheduled < now)
        if is_overdue:
            overdue += 1
        if task.status == "pending":
            pending += 1
        elif task.status == "done":
            done += 1
        elif task.status == "skipped":
            skipped += 1
        tasks.append(
            {
                "id": task.id,
                "planting_id": task.planting_id,
                "allocation_id": task.allocation_id,
                "rack_id": task.rack_id,
                "slot_number": task.slot_number,
                "plant_name": _plant_name(plant),
                "plant_names": plant.names,
                "scheduled_at": scheduled,
                "scheduled_local": scheduled.astimezone(zone).isoformat() if scheduled else None,
                "planned_ml": int(task.planned_ml),
                "actual_ml": task.actual_ml,
                "task_type": task.task_type,
                "status": task.status,
                "overdue": is_overdue,
                "completed_at": completed,
                "completed_local": completed.astimezone(zone).isoformat() if completed else None,
                "note": task.note,
                "watering_adjustment_percent": int(allocation.watering_adjustment_percent or 0) if allocation else 0,
            }
        )

    return {
        "date": selected.isoformat(),
        "timezone": str(zone),
        "summary": {
            "total": len(tasks),
            "pending": pending,
            "overdue": overdue,
            "done": done,
            "skipped": skipped,
        },
        "tasks": tasks,
    }


@router.post("/{task_id}/complete")
async def complete_watering_task(
    task_id: str,
    payload: CompleteWateringIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    task = (
        await session.execute(
            select(WateringTask)
            .where(WateringTask.id == task_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Watering task not found")
    if task.status == "done":
        return {"ok": True, "status": "done", "actual_ml": task.actual_ml}
    if task.status != "pending":
        raise HTTPException(status_code=409, detail="Only a pending watering can be completed")

    now = datetime.now(timezone.utc)
    actual = int(payload.actual_ml or task.planned_ml)
    task.actual_ml = actual
    task.status = "done"
    task.completed_at = now
    task.completed_by_admin_id = admin.id
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="complete_watering",
            target_type="watering_task",
            target_id=task.id,
            details={
                "planned_ml": task.planned_ml,
                "actual_ml": actual,
                "rack_id": task.rack_id,
                "slot_number": task.slot_number,
                "task_type": task.task_type,
            },
        )
    )
    await session.commit()
    return {"ok": True, "status": "done", "actual_ml": actual, "completed_at": now}


@router.post("/{task_id}/skip")
async def skip_watering_task(
    task_id: str,
    payload: SkipWateringIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    task = (
        await session.execute(
            select(WateringTask)
            .where(WateringTask.id == task_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Watering task not found")
    if task.status == "skipped":
        return {"ok": True, "status": "skipped"}
    if task.status != "pending":
        raise HTTPException(status_code=409, detail="Only a pending watering can be skipped")

    reason = payload.reason.strip() or "Skipped by administrator"
    task.status = "skipped"
    task.completed_at = datetime.now(timezone.utc)
    task.completed_by_admin_id = admin.id
    task.note = reason
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="skip_watering",
            target_type="watering_task",
            target_id=task.id,
            details={
                "reason": reason,
                "rack_id": task.rack_id,
                "slot_number": task.slot_number,
                "planned_ml": task.planned_ml,
                "task_type": task.task_type,
            },
        )
    )
    await session.commit()
    return {"ok": True, "status": "skipped"}
