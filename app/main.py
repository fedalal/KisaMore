from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import runtime
from .bootstrap import ensure_db_tables, ensure_db_racks
from .scheduler import Scheduler

from .routes_state import router as state_router
from .routes_manual import router as manual_router
from .routes_schedule import router as schedule_router
from .routes_config import router as config_router
from .routes_inputs import router as inputs_router
from .routes_camera import router as camera_router
from .sensor_history_service import SensorHistoryService
from .routes_sensor_history import router as sensor_history_router
from .camera_capture_service import camera_capture_service
from .camera_manager import camera_manager


import subprocess
from fastapi import HTTPException

app = FastAPI(title="Система KisaMore — Raspberry Pi")

app.include_router(state_router)
app.include_router(manual_router)
app.include_router(schedule_router)
app.include_router(config_router)
app.include_router(inputs_router)
app.include_router(sensor_history_router)
app.include_router(camera_router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

scheduler = Scheduler(runtime)
sensor_history_service = SensorHistoryService(interval_sec=60)  # раз в 1 минуту

@app.on_event("startup")
async def on_startup():
    # 1) конфиг + драйвер
    await runtime.init_runtime(active_low=True)

    # 2) база
    await ensure_db_tables()
    await ensure_db_racks(runtime.cfg.racks_count if runtime.cfg else 4)

    # 2.5) FAIL-SAFE + восстановление состояния
    # Сначала выключаем всё (на случай залипаний), затем сразу же включаем то,
    # что должно быть включено (manual) или что требуется по расписанию (schedule).
    await runtime.safety_reset_and_sync_relays()

    # 3) планировщик
    await scheduler.start()

    # 4) запись истории в БД
    await sensor_history_service.start()

    # 5) отправка фото с камер в Google Drive
    await camera_capture_service.start()

@app.on_event("shutdown")
async def on_shutdown():
    await camera_capture_service.stop()
    camera_manager.stop_all()

    await scheduler.stop()

    await sensor_history_service.stop()

    if runtime.inputs:
        runtime.inputs.close()

@app.get("/charts", response_class=HTMLResponse)
async def charts_page(request: Request):
    return templates.TemplateResponse("charts.html", {"request": request})

@app.get("/cameras", response_class=HTMLResponse)
async def cameras_page(request: Request):
    return templates.TemplateResponse("cameras.html", {"request": request})

@app.post("/api/system/shutdown")
async def shutdown_pi():
    try:
        print("Shutting down KisaMore")
        subprocess.Popen(["sudo", "/sbin/shutdown", "-h", "now"])
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
