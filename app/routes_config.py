from fastapi import APIRouter
from .hw_config import HWConfig, save_config
from .schemas import HWConfigOut
from . import runtime
from .bootstrap import ensure_db_racks

router = APIRouter(prefix="/api", tags=["config"])

@router.get("/config", response_model=HWConfigOut)
async def get_config():
    return runtime.cfg.model_dump() if runtime.cfg else {"racks_count": 4, "racks": {}}

@router.post("/config")
async def set_config(payload: HWConfig):
    save_config(payload)
    await runtime.init_runtime(active_low=True)
    await ensure_db_racks(runtime.cfg.racks_count)
    return {"ok": True}
