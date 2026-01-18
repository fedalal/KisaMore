from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from .db import SessionLocal
from .models import RackSchedule
from .schemas import RackSchedulePayload
from . import runtime

router = APIRouter(prefix="/api", tags=["schedule"])

def _empty():
    return {"mon": [], "tue": [], "wed": [], "thu": [], "fri": [], "sat": [], "sun": []}

def _ensure_rack(rack_id: int):
    if runtime.cfg and (rack_id < 1 or rack_id > runtime.cfg.racks_count):
        raise HTTPException(404, "rack not found")

@router.get("/rack/{rack_id}/schedule")
async def get_schedule(rack_id: int):
    _ensure_rack(rack_id)
    async with SessionLocal() as s:
        sch = (await s.execute(select(RackSchedule).where(RackSchedule.rack_id == rack_id))).scalar_one_or_none()
        if not sch:
            return {"light": _empty(), "water": _empty()}
        data = sch.schedule_json or {}
        data.setdefault("light", _empty())
        data.setdefault("water", _empty())
        for k in _empty().keys():
            data["light"].setdefault(k, [])
            data["water"].setdefault(k, [])
        return data

@router.post("/rack/{rack_id}/schedule")
async def set_schedule(rack_id: int, payload: RackSchedulePayload):
    _ensure_rack(rack_id)
    async with SessionLocal() as s:
        sch = (await s.execute(select(RackSchedule).where(RackSchedule.rack_id == rack_id))).scalar_one_or_none()
        data = payload.model_dump()
        if sch:
            sch.schedule_json = data
        else:
            s.add(RackSchedule(rack_id=rack_id, schedule_json=data))
        await s.commit()
    return {"ok": True}
