from fastapi import APIRouter, HTTPException
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

    # Валидация: одно реле нельзя назначать разным устройствам
    # (Стеллаж N — Свет/Полив). Проверяем на сервере на случай обхода UI.
    used: dict[int, list[str]] = {}
    for rack_id, rack in payload.racks.items():
        try:
            rid = int(rack_id)
        except Exception:
            rid = rack_id  # type: ignore

        def add(relay_num: int, label: str):
            used.setdefault(int(relay_num), []).append(label)

        add(rack.light_relay, f"Стеллаж {rid} — Свет")
        add(rack.water_relay, f"Стеллаж {rid} — Полив")

    dups = {k: v for k, v in used.items() if len(v) > 1}
    if dups:
        lines = [f"Реле {relay}: {', '.join(labels)}" for relay, labels in sorted(dups.items())]
        raise HTTPException(status_code=400, detail="Одно и то же реле назначено нескольким устройствам: " + " | ".join(lines))

    save_config(payload)

    # переинициализируем драйвер/конфиг в runtime
    await runtime.init_runtime(active_low=True)
    await ensure_db_racks(runtime.cfg.racks_count)
    return {"ok": True}
