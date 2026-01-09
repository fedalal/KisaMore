from fastapi import APIRouter
from sqlalchemy import select
from .db import SessionLocal
from .models import RackState
from .schemas import RackStateOut
from . import runtime

router = APIRouter(prefix="/api", tags=["state"])

@router.get("/state", response_model=list[RackStateOut])
async def get_state():
    max_racks = runtime.cfg.racks_count if runtime.cfg else 4
    async with SessionLocal() as s:
        rows = (await s.execute(select(RackState).order_by(RackState.rack_id))).scalars().all()
        rows = [r for r in rows if r.rack_id <= max_racks]
        return [
            RackStateOut(
                rack_id=r.rack_id,
                light_on=r.light_on,
                water_on=r.water_on,
                light_mode=r.light_mode,
                water_mode=r.water_mode,
            )
            for r in rows
        ]
