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
    # UI сейчас сохраняет только часть конфига.
    # Поэтому секции, которые не редактируются в интерфейсе,
    # нужно сохранять из текущего config/kisamore.yaml.
    existing = runtime.cfg or load_config()

    if payload.rs485 is None and existing.rs485 is not None:
        payload = payload.model_copy(update={"rs485": existing.rs485})

    if not payload.cameras and existing.cameras:
        payload = payload.model_copy(update={"cameras": existing.cameras})

    if not payload.level_sensors and existing.level_sensors:
        payload = payload.model_copy(update={"level_sensors": existing.level_sensors})

    # camera_capture в UI камеры отдаётся частично: разрешение и JPEG quality.
    # Обновляем только реально присланные поля, а остальные параметры (интервал,
    # Google Drive, архив и т.д.) сохраняем из текущего YAML.
    capture_fields = payload.camera_capture.model_fields_set
    capture_updates = {
        field: getattr(payload.camera_capture, field)
        for field in capture_fields
    }
    merged_capture = existing.camera_capture.model_copy(update=capture_updates)
    payload = payload.model_copy(update={"camera_capture": merged_capture})

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

    # Проверка: все камеры, назначенные полке, должны существовать.
    for rack_id, rack in payload.racks.items():
        assigned = list(rack.camera_ids or [])
        if rack.camera_id and rack.camera_id not in assigned:
            assigned.insert(0, rack.camera_id)
        for camera_id in assigned:
            if camera_id not in payload.cameras:
                raise HTTPException(
                    status_code=400,
                    detail=f"Для стеллажа {rack_id} выбрана несуществующая камера: {camera_id}",
                )
        if rack.camera_id and assigned and assigned[0] != rack.camera_id:
            raise HTTPException(
                status_code=400,
                detail=f"Основная камера стеллажа {rack_id} должна быть первой в camera_ids",
            )

    dups = {k: v for k, v in used.items() if len(v) > 1}

    if dups:
        lines = [
            f"Реле {relay}: {', '.join(labels)}"
            for relay, labels in sorted(dups.items())
        ]
        raise HTTPException(
            status_code=400,
            detail="Одно и то же реле назначено нескольким устройствам: " + " | ".join(lines),
        )

    save_config(payload)

    # переинициализируем драйвер/конфиг в runtime
    await runtime.init_runtime(active_low=True)
    await ensure_db_racks(runtime.cfg.racks_count)

    return {"ok": True}
