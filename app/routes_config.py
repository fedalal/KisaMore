from fastapi import APIRouter
from .hw_config import HWConfig, save_config, load_config
from .schemas import HWConfigOut
from . import runtime
from .bootstrap import ensure_db_racks

router = APIRouter(prefix="/api", tags=["config"])

@router.get("/config", response_model=HWConfigOut)
async def get_config():
    return runtime.cfg.model_dump() if runtime.cfg else {"racks_count": 4, "racks": {}}

@router.post("/config")
async def set_config(payload: HWConfig):
    # UI сейчас сохраняет только racks_count + racks, без rs485.
    # Чтобы не затирать rs485-секцию в config/kisamore.yaml, сохраняем её из текущего конфига,
    # если в payload она отсутствует.
    existing = runtime.cfg or load_config()
    if payload.rs485 is None and existing.rs485 is not None:
        payload = payload.model_copy(update={"rs485": existing.rs485})

    save_config(payload)

    # переинициализируем драйвер/конфиг в runtime
    await runtime.init_runtime(active_low=True)
    await ensure_db_racks(runtime.cfg.racks_count)
    return {"ok": True}
