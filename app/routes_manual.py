from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from .db import SessionLocal
from .models import RackState
from .schemas import ManualSetIn, ModeSetIn
from . import runtime

router = APIRouter(prefix="/api", tags=["manual"])

def _ensure_runtime():
    if not runtime.cfg or not runtime.driver:
        raise HTTPException(500, "runtime not initialized")

def _ensure_rack(rack_id: int):
    _ensure_runtime()
    if rack_id < 1 or rack_id > runtime.cfg.racks_count:
        raise HTTPException(404, "rack not found")

@router.post("/rack/{rack_id}/light/manual")
async def manual_light(rack_id: int, payload: ManualSetIn):
    _ensure_rack(rack_id)
    async with SessionLocal() as s:
        st = (await s.execute(select(RackState).where(RackState.rack_id == rack_id))).scalar_one_or_none()
        if not st:
            raise HTTPException(404, "rack not found")
        st.light_mode = "manual"
        st.light_on = payload.on
        await s.commit()

    relay_id = runtime.cfg.racks[str(rack_id)].light_relay
    await runtime.driver.set_relay(relay_id, payload.on)
    return {"ok": True}

@router.post("/rack/{rack_id}/water/manual")
async def manual_water(rack_id: int, payload: ManualSetIn):
    _ensure_rack(rack_id)
    async with SessionLocal() as s:
        st = (await s.execute(select(RackState).where(RackState.rack_id == rack_id))).scalar_one_or_none()
        if not st:
            raise HTTPException(404, "rack not found")
        st.water_mode = "manual"
        st.water_on = payload.on
        await s.commit()

    relay_id = runtime.cfg.racks[str(rack_id)].water_relay
    await runtime.driver.set_relay(relay_id, payload.on)
    return {"ok": True}

@router.post("/rack/{rack_id}/light/mode")
async def set_light_mode(rack_id: int, payload: ModeSetIn):
    _ensure_rack(rack_id)
    async with SessionLocal() as s:
        st = (await s.execute(select(RackState).where(RackState.rack_id == rack_id))).scalar_one_or_none()
        if not st:
            raise HTTPException(404, "rack not found")
        st.light_mode = payload.mode
        await s.commit()
    return {"ok": True}

@router.post("/rack/{rack_id}/water/mode")
async def set_water_mode(rack_id: int, payload: ModeSetIn):
    _ensure_rack(rack_id)
    async with SessionLocal() as s:
        st = (await s.execute(select(RackState).where(RackState.rack_id == rack_id))).scalar_one_or_none()
        if not st:
            raise HTTPException(404, "rack not found")
        st.water_mode = payload.mode
        await s.commit()
    return {"ok": True}
