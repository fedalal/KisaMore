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




import subprocess
from fastapi import HTTPException

app = FastAPI(title="Система KisaMore — Raspberry Pi")

app.include_router(state_router)
app.include_router(manual_router)
app.include_router(schedule_router)
app.include_router(config_router)
app.include_router(inputs_router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

scheduler = Scheduler(runtime)

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

@app.on_event("shutdown")
async def on_shutdown():
    await scheduler.stop()
    if runtime.inputs:
        runtime.inputs.close()

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
