#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import threading
import time
from datetime import datetime
from typing import Any

import cv2
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

from app.camera_profiles import (
    camera_profile_path,
    load_camera_profile,
    profile_controls,
    profile_format,
    save_camera_profile,
)


def run_cmd(cmd: list[str], timeout: float = 5.0) -> str:
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "command failed")
    return result.stdout


def parse_ctrls(text: str) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    main_re = re.compile(
        r"^\s*([A-Za-z0-9_]+)\s+0x[0-9a-fA-F]+\s+\(([^)]+)\)\s*:\s*(.*)$"
    )
    menu_re = re.compile(r"^\s*(-?\d+):\s*(.+?)\s*$")

    for raw in text.splitlines():
        match = main_re.match(raw)
        if match:
            name, kind, tail = match.groups()
            current = {
                "name": name,
                "type": kind.strip(),
                "menu": [],
                "readonly": "read-only" in tail,
                "inactive": "inactive" in tail,
                "raw": tail.strip(),
            }
            for key in ("min", "max", "step", "default", "value"):
                value_match = re.search(rf"\b{key}=(-?\d+)", tail)
                if value_match:
                    current[key] = int(value_match.group(1))
            controls.append(current)
            continue

        if current and current["type"] == "menu":
            menu_match = menu_re.match(raw)
            if menu_match:
                current["menu"].append(
                    {
                        "value": int(menu_match.group(1)),
                        "label": menu_match.group(2).strip(),
                    }
                )

    return controls


def get_controls(device: str) -> list[dict[str, Any]]:
    return parse_ctrls(
        run_cmd(["v4l2-ctl", "--device", device, "--list-ctrls-menus"])
    )


def control_value(device: str, name: str) -> int | None:
    try:
        text = run_cmd(
            ["v4l2-ctl", "--device", device, "--get-ctrl", name],
            timeout=3,
        )
        match = re.search(r":\s*(-?\d+)\s*$", text.strip())
        return int(match.group(1)) if match else None
    except Exception:
        return None


def current_format(device: str) -> dict[str, Any]:
    fmt_text = run_cmd(["v4l2-ctl", "--device", device, "--get-fmt-video"])
    width = height = None
    pixel_format = None

    match = re.search(r"Width/Height\s*:\s*(\d+)/(\d+)", fmt_text)
    if match:
        width, height = int(match.group(1)), int(match.group(2))

    match = re.search(r"Pixel Format\s*:\s*'([^']+)'", fmt_text)
    if match:
        pixel_format = match.group(1)

    fps = None
    try:
        parm = run_cmd(["v4l2-ctl", "--device", device, "--get-parm"])
        match = re.search(r"Frames per second:\s*([0-9.]+)", parm)
        if match:
            fps = float(match.group(1))
    except Exception:
        pass

    return {
        "width": width,
        "height": height,
        "pixelformat": pixel_format,
        "fps": fps,
    }


def set_format(device: str, width: int, height: int, pixel_format: str, fps: int):
    run_cmd(
        [
            "v4l2-ctl",
            "--device",
            device,
            "--set-fmt-video",
            f"width={width},height={height},pixelformat={pixel_format}",
        ]
    )
    run_cmd(
        [
            "v4l2-ctl",
            "--device",
            device,
            "--set-parm",
            str(fps),
        ]
    )


class CameraStream:
    def __init__(self, device: str, width: int, height: int, pixel_format: str, fps: int):
        self.device = device
        self.width = int(width)
        self.height = int(height)
        self.pixel_format = str(pixel_format)
        self.fps = int(fps)

        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.cap: cv2.VideoCapture | None = None
        self.frame = None
        self.last_error: str | None = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)
        self.thread = None

        with self.lock:
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None

    def restart(self):
        self.stop()
        self.start()

    def wait_for_frame(self, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.lock:
                if self.frame is not None:
                    return True
                error = self.last_error
            if error:
                return False
            time.sleep(0.05)
        return False

    def _run(self):
        try:
            cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
            if not cap.isOpened():
                raise RuntimeError(f"Не удалось открыть {self.device}")

            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.pixel_format))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.fps)
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            with self.lock:
                self.cap = cap
                self.frame = None
                self.last_error = None

            while not self.stop_event.is_set():
                # Never run v4l2-ctl concurrently with VideoCapture.read().
                with self.lock:
                    ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.03)
                    continue
                with self.lock:
                    self.frame = frame

        except Exception as exc:
            with self.lock:
                self.last_error = str(exc)
        finally:
            with self.lock:
                if self.cap is not None:
                    try:
                        self.cap.release()
                    except Exception:
                        pass
                self.cap = None

    def set_control(self, name: str, value: int):
        with self.lock:
            run_cmd(
                [
                    "v4l2-ctl",
                    "--device",
                    self.device,
                    "--set-ctrl",
                    f"{name}={int(value)}",
                ],
                timeout=4,
            )

    def jpeg(self, *, max_width: int, quality: int) -> bytes | None:
        with self.lock:
            if self.frame is None:
                return None
            frame = self.frame.copy()

        height, width = frame.shape[:2]
        if max_width > 0 and width > max_width:
            scale = max_width / float(width)
            frame = cv2.resize(
                frame,
                (max_width, max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA,
            )

        ok, encoded = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)],
        )
        return bytes(encoded) if ok else None


class ControlUpdate(BaseModel):
    name: str
    value: int


class FormatUpdate(BaseModel):
    width: int
    height: int
    pixelformat: str = "MJPG"
    fps: int = 30


def apply_saved_controls(stream: CameraStream, controls: dict[str, int]):
    if not controls:
        return

    supported = {item["name"]: item for item in get_controls(stream.device)}
    priority = [
        "focus_automatic_continuous",
        "focus_auto",
        "white_balance_automatic",
        "white_balance_temperature_auto",
        "auto_exposure",
    ]
    names = [name for name in priority if name in controls]
    names.extend(name for name in controls if name not in names)

    auto_focus = controls.get(
        "focus_automatic_continuous",
        controls.get("focus_auto"),
    )
    auto_wb = controls.get(
        "white_balance_automatic",
        controls.get("white_balance_temperature_auto"),
    )
    auto_exposure = controls.get("auto_exposure")

    for name in names:
        meta = supported.get(name)
        if not meta or meta.get("readonly") or meta.get("inactive"):
            continue
        if name == "focus_absolute" and auto_focus == 1:
            continue
        if name == "white_balance_temperature" and auto_wb == 1:
            continue
        if name == "exposure_time_absolute" and auto_exposure != 1:
            continue
        try:
            stream.set_control(name, controls[name])
        except Exception as exc:
            print(f"[camera-tuner] cannot restore {name}={controls[name]}: {exc}")


HTML = r"""
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Camera Tuner</title>
<style>
:root{font-family:Inter,system-ui,Arial,sans-serif;color:#152033;background:#eef2f7}*{box-sizing:border-box}body{margin:0}
header{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid #d9e0ea;padding:12px 18px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
header h1{font-size:20px;margin:0 12px 0 0}button{border:1px solid #cbd5e1;background:#fff;border-radius:9px;padding:9px 13px;font-weight:700;cursor:pointer}.primary{background:#2563eb;color:#fff;border-color:#2563eb}.danger{color:#b91c1c}.status{font-size:13px;color:#526175}
main{display:grid;grid-template-columns:minmax(480px,1.35fr) minmax(420px,1fr);gap:14px;padding:14px}.card{background:#fff;border:1px solid #d9e0ea;border-radius:14px;padding:14px;box-shadow:0 4px 16px rgba(20,35,60,.05)}.previewWrap{position:sticky;top:78px}.preview{width:100%;display:block;border-radius:10px;background:#111;min-height:280px;object-fit:contain}
.row{display:grid;grid-template-columns:190px 1fr 90px;gap:10px;align-items:center;padding:7px 0;border-bottom:1px solid #edf0f4}.name{font-size:13px;font-weight:700}.meta,.small{font-size:11px;color:#718096;font-weight:500}input[type=range]{width:100%}input[type=number],select,input[type=text]{width:100%;padding:7px 8px;border:1px solid #cbd5e1;border-radius:7px;background:#fff}.checkboxCell{display:flex;align-items:center}.sectionTitle{font-weight:800;margin:6px 0 10px}.formatGrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}pre{white-space:pre-wrap;background:#0f172a;color:#e2e8f0;padding:12px;border-radius:10px;max-height:260px;overflow:auto;font-size:12px}.disabled{opacity:.45}@media(max-width:1000px){main{grid-template-columns:1fr}.previewWrap{position:static}}
</style>
</head>
<body>
<header>
  <h1>Camera Tuner · <span id="cameraName">…</span></h1>
  <button class="primary" onclick="saveProfile()">Сохранить параметры</button>
  <button onclick="downloadSnapshot()">Полный кадр</button>
  <button onclick="refreshState()">Обновить</button>
  <button class="danger" onclick="resetDefaults()">По умолчанию</button>
  <span id="status" class="status">загрузка…</span>
</header>
<main>
  <div>
    <div class="card previewWrap">
      <div class="sectionTitle">Изображение с камеры</div>
      <img id="preview" class="preview" src="/stream">
      <div class="small" id="cameraInfo" style="margin-top:9px"></div>
      <div class="small" id="profileInfo" style="margin-top:5px"></div>
    </div>
    <div class="card" style="margin-top:14px">
      <div class="sectionTitle">Формат камеры</div>
      <div class="formatGrid">
        <label><div class="small">Ширина</div><input id="width" type="number"></label>
        <label><div class="small">Высота</div><input id="height" type="number"></label>
        <label><div class="small">Формат</div><input id="pixelformat" type="text"></label>
        <label><div class="small">FPS</div><input id="fps" type="number"></label>
      </div>
      <button style="margin-top:10px" onclick="applyFormat()">Применить формат</button>
    </div>
    <div class="card" style="margin-top:14px">
      <div class="sectionTitle">Команда текущего профиля</div>
      <pre id="shellCommand">—</pre>
    </div>
  </div>
  <div class="card">
    <div class="sectionTitle">Все V4L2-параметры</div>
    <div class="small" style="margin-bottom:8px">Изменения применяются непосредственно к Linux V4L2 driver.</div>
    <div id="controls"></div>
  </div>
</main>
<script>
let state=null;let pending=new Map();
function esc(s){return String(s??"").replace(/[&<>\"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
function setStatus(s){document.getElementById("status").textContent=s;}
async function api(path,opts={}){const r=await fetch(path,opts);if(!r.ok)throw new Error(await r.text());return await r.json();}
function buildControl(c){const disabled=c.readonly||c.inactive;const id="ctrl_"+c.name;let widget="";if(c.type==="bool"){widget=`<div class="checkboxCell"><input id="${id}" type="checkbox" ${c.value?"checked":""} ${disabled?"disabled":""} onchange="setControl('${esc(c.name)}',this.checked?1:0)"></div><div></div>`;}else if(c.type==="menu"){const opts=(c.menu||[]).map(m=>`<option value="${m.value}" ${m.value===c.value?"selected":""}>${m.value}: ${esc(m.label)}</option>`).join("");widget=`<select id="${id}" ${disabled?"disabled":""} onchange="setControl('${esc(c.name)}',Number(this.value))">${opts}</select><div></div>`;}else if(Number.isFinite(c.min)&&Number.isFinite(c.max)){const step=c.step||1;widget=`<input id="${id}_range" type="range" min="${c.min}" max="${c.max}" step="${step}" value="${c.value}" ${disabled?"disabled":""} oninput="document.getElementById('${id}_num').value=this.value;queueControl('${esc(c.name)}',Number(this.value))"><input id="${id}_num" type="number" min="${c.min}" max="${c.max}" step="${step}" value="${c.value}" ${disabled?"disabled":""} onchange="syncNumber('${esc(c.name)}',this.value,${c.min},${c.max})">`;}else{widget=`<input id="${id}_num" type="number" value="${c.value??0}" ${disabled?"disabled":""} onchange="setControl('${esc(c.name)}',Number(this.value))"><div></div>`;}return `<div class="row ${disabled?"disabled":""}"><div class="name">${esc(c.name)}<div class="meta">${esc(c.type)} · default=${c.default??"?"}${c.inactive?" · inactive":""}</div></div>${widget}</div>`;}
function render(){document.getElementById("cameraName").textContent=state.camera_name;document.getElementById("controls").innerHTML=state.controls.map(buildControl).join("");document.getElementById("width").value=state.format.width||"";document.getElementById("height").value=state.format.height||"";document.getElementById("pixelformat").value=state.format.pixelformat||"MJPG";document.getElementById("fps").value=state.format.fps||30;document.getElementById("cameraInfo").textContent=`${state.device} · ${state.format.width}×${state.format.height} · ${state.format.pixelformat} · ${state.format.fps??"?"} fps`;document.getElementById("profileInfo").textContent=`Профиль: ${state.profile_path}${state.profile_loaded?" · загружен при запуске":" · ещё не сохранён"}`;document.getElementById("shellCommand").textContent=state.shell_command||"—";}
async function refreshState(){try{setStatus("чтение параметров…");state=await api("/api/state");render();setStatus("готово");}catch(e){setStatus("ошибка: "+e.message);}}
function queueControl(name,value){clearTimeout(pending.get(name));pending.set(name,setTimeout(()=>setControl(name,value),120));}
function syncNumber(name,value,min,max){let v=Number(value);v=Math.max(min,Math.min(max,v));const r=document.getElementById("ctrl_"+name+"_range");if(r)r.value=v;setControl(name,v);}
async function setControl(name,value){try{setStatus(`${name}=${value}…`);const result=await api("/api/control",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,value})});setStatus(`${name}=${result.value}`);setTimeout(refreshState,120);}catch(e){setStatus("ошибка: "+e.message);}}
async function applyFormat(){try{setStatus("перезапуск камеры…");await api("/api/format",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({width:Number(document.getElementById("width").value),height:Number(document.getElementById("height").value),pixelformat:document.getElementById("pixelformat").value.trim(),fps:Number(document.getElementById("fps").value)})});document.getElementById("preview").src="/stream?t="+Date.now();setTimeout(refreshState,800);}catch(e){setStatus("ошибка: "+e.message);}}
async function saveProfile(){try{setStatus("сохранение…");const result=await api("/api/save",{method:"POST"});document.getElementById("shellCommand").textContent=result.shell_command;document.getElementById("profileInfo").textContent=`Профиль: ${result.path} · сохранён`;setStatus("сохранено");}catch(e){setStatus("ошибка: "+e.message);}}
async function resetDefaults(){if(!confirm("Вернуть доступные controls к default?"))return;try{setStatus("сброс…");await api("/api/reset-defaults",{method:"POST"});setTimeout(refreshState,400);}catch(e){setStatus("ошибка: "+e.message);}}
function downloadSnapshot(){window.open("/snapshot?t="+Date.now(),"_blank");}
refreshState();
</script>
</body>
</html>
"""


def make_app(args):
    saved_profile = load_camera_profile(args.camera_name)

    if saved_profile:
        width, height, pixel_format, fps = profile_format(
            saved_profile,
            default_width=args.width,
            default_height=args.height,
            default_pixelformat=args.pixelformat,
            default_fps=args.fps,
        )
        try:
            set_format(args.device, width, height, pixel_format, fps)
        except Exception as exc:
            print(f"[camera-tuner] cannot restore saved format: {exc}")
    else:
        try:
            fmt = current_format(args.device)
            width = int(fmt.get("width") or args.width)
            height = int(fmt.get("height") or args.height)
            pixel_format = str(fmt.get("pixelformat") or args.pixelformat)
            fps = int(round(float(fmt.get("fps") or args.fps)))
        except Exception:
            width, height, pixel_format, fps = args.width, args.height, args.pixelformat, args.fps

    stream = CameraStream(args.device, width, height, pixel_format, fps)
    app = FastAPI(title=f"Camera Tuner · {args.camera_name}")

    @app.on_event("startup")
    def startup():
        stream.start()
        stream.wait_for_frame(5)
        if saved_profile:
            apply_saved_controls(stream, profile_controls(saved_profile))
            time.sleep(0.2)
            print(f"[camera-tuner] loaded profile {camera_profile_path(args.camera_name)}")

    @app.on_event("shutdown")
    def shutdown():
        stream.stop()

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML

    @app.get("/api/state")
    def state():
        controls = get_controls(args.device)
        fmt = current_format(args.device)
        control_map = {
            item["name"]: item.get("value")
            for item in controls
            if item.get("value") is not None
        }
        from app.camera_profiles import shell_command_for_profile
        return {
            "camera_name": args.camera_name,
            "device": args.device,
            "controls": controls,
            "format": fmt,
            "profile_path": str(camera_profile_path(args.camera_name)),
            "profile_loaded": saved_profile is not None,
            "shell_command": shell_command_for_profile(
                device=args.device,
                fmt=fmt,
                controls=control_map,
            ),
        }

    @app.post("/api/control")
    def update_control(update: ControlUpdate):
        controls = {item["name"]: item for item in get_controls(args.device)}
        meta = controls.get(update.name)
        if not meta:
            raise HTTPException(404, f"Unknown control: {update.name}")
        if meta.get("readonly") or meta.get("inactive"):
            raise HTTPException(400, f"Control is not writable: {update.name}")

        try:
            stream.set_control(update.name, update.value)
        except Exception as exc:
            raise HTTPException(500, str(exc))

        return {
            "ok": True,
            "name": update.name,
            "value": control_value(args.device, update.name),
        }

    @app.post("/api/format")
    def update_format(update: FormatUpdate):
        if update.width < 160 or update.height < 120:
            raise HTTPException(400, "Invalid resolution")
        if len(update.pixelformat) != 4:
            raise HTTPException(400, "Pixel format must be a fourcc such as MJPG")
        if update.fps < 1 or update.fps > 120:
            raise HTTPException(400, "Invalid FPS")

        try:
            stream.stop()
            set_format(
                args.device,
                update.width,
                update.height,
                update.pixelformat,
                update.fps,
            )
            stream.width = update.width
            stream.height = update.height
            stream.pixel_format = update.pixelformat
            stream.fps = update.fps
            stream.start()
            stream.wait_for_frame(5)
        except Exception as exc:
            stream.start()
            raise HTTPException(500, str(exc))

        return {"ok": True}

    @app.post("/api/reset-defaults")
    def reset_defaults():
        errors = []
        for item in get_controls(args.device):
            if item.get("readonly") or item.get("inactive") or "default" not in item:
                continue
            try:
                stream.set_control(item["name"], int(item["default"]))
            except Exception as exc:
                errors.append(f"{item['name']}: {exc}")
        return {"ok": not errors, "errors": errors}

    @app.post("/api/save")
    def save():
        controls_meta = get_controls(args.device)
        values: dict[str, int] = {}
        for item in controls_meta:
            value = control_value(args.device, item["name"])
            if value is not None:
                values[item["name"]] = value

        fmt = current_format(args.device)
        json_path, shell_path, profile, command = save_camera_profile(
            camera_name=args.camera_name,
            device=args.device,
            fmt=fmt,
            controls=values,
            saved_at=datetime.now().isoformat(timespec="seconds"),
        )
        return {
            "ok": True,
            "path": str(json_path),
            "shell_path": str(shell_path),
            "profile": profile,
            "shell_command": command,
        }

    @app.get("/snapshot")
    def snapshot():
        jpeg = stream.jpeg(max_width=0, quality=95)
        if not jpeg:
            raise HTTPException(503, "No camera frame")
        return Response(
            content=jpeg,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/stream")
    def mjpeg():
        def generate():
            while True:
                jpeg = stream.jpeg(max_width=args.preview_width, quality=88)
                if jpeg:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Cache-Control: no-store\r\n\r\n"
                        + jpeg
                        + b"\r\n"
                    )
                time.sleep(0.10)

        return StreamingResponse(
            generate(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    return app


def parse_args():
    parser = argparse.ArgumentParser(
        description="Headless Linux V4L2 camera tuner shared with KisaMore"
    )
    parser.add_argument(
        "--camera-name",
        required=True,
        help="Stable KisaMore camera id, for example camera_1",
    )
    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--width", type=int, default=2592)
    parser.add_argument("--height", type=int, default=1944)
    parser.add_argument("--pixelformat", default="MJPG")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--preview-width", type=int, default=1600)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    uvicorn.run(
        make_app(args),
        host=args.host,
        port=args.port,
        log_level="info",
    )
