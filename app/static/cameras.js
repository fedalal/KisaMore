let cfgState = null;
let picking = { cameraId: null, points: [] };

async function api(path, method="GET", body=null){
  const res = await fetch(path, {
    method,
    headers: body ? {"Content-Type":"application/json"} : {},
    body: body ? JSON.stringify(body) : null
  });
  if(!res.ok){
    const t = await res.text();
    throw new Error(t || res.statusText);
  }
  return await res.json();
}

function escapeHtml(value){
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setConn(ok){
  const el = document.getElementById("conn");
  if(el) el.textContent = ok ? "🟢 онлайн" : "🔴 нет связи";
}

function formatWarpPoints(points){
  if(!Array.isArray(points) || points.length !== 8) return "";
  return `${points[0]},${points[1]} ${points[2]},${points[3]} ${points[4]},${points[5]} ${points[6]},${points[7]}`;
}

function parseWarpPoints(value){
  const text = String(value || "").trim();
  if(!text) return null;

  const nums = text
    .replace(/[;]/g, " ")
    .split(/[\s,]+/)
    .map(v => Number(v))
    .filter(v => Number.isFinite(v));

  if(nums.length !== 8){
    alert("Нужно указать 4 точки: x1,y1 x2,y2 x3,y3 x4,y4");
    return undefined;
  }

  return nums;
}

function cameraIds(){
  return Object.keys(cfgState?.cameras || {}).sort();
}

function newCameraId(){
  let i = 1;
  while((cfgState.cameras || {})[`camera_${i}`]) i++;
  return `camera_${i}`;
}

function changeCamera(cameraId, field, value){
  if(!cfgState.cameras[cameraId]) return;
  cfgState.cameras[cameraId][field] = value;
}

function changeCameraNumber(cameraId, field, value){
  if(!cfgState.cameras[cameraId]) return;

  const v = String(value ?? "").trim();
  if(v === ""){
    cfgState.cameras[cameraId][field] = null;
    return;
  }

  const n = Number(v);
  if(!Number.isFinite(n)){
    alert("Нужно указать число");
    renderCameras();
    return;
  }

  cfgState.cameras[cameraId][field] = n;
}

function changeWarpText(cameraId, value){
  const points = parseWarpPoints(value);
  if(points === undefined){
    renderCameras();
    return;
  }
  cfgState.cameras[cameraId].warp_points = points;
  renderCameras();
}

function addCamera(){
  const id = newCameraId();
  cfgState.cameras[id] = {
    name: `Камера ${cameraIds().length + 1}`,
    device: `/dev/video${cameraIds().length}`,
    flip_vertical: false,
    flip_horizontal: false,
    warp_enabled: false,
    warp_points: null,
    autofocus_enabled: true,
    focus_absolute: 512,
    white_balance_auto: true,
    white_balance_temperature: 4
  };
  renderCameras();
}

function deleteCamera(cameraId){
  const usedBy = Object.entries(cfgState.racks || {})
    .filter(([_, rack]) => rack.camera_id === cameraId)
    .map(([rackId]) => rackId);

  if(usedBy.length){
    alert(`Эта камера используется стеллажами: ${usedBy.join(", ")}. Сначала выбери другую камеру в настройках оборудования.`);
    return;
  }

  if(!confirm(`Удалить камеру ${cameraId}?`)) return;
  delete cfgState.cameras[cameraId];
  renderCameras();
}

function startPickPoints(cameraId){
  picking = { cameraId, points: [] };
  renderCameras();
}

function resetPoints(cameraId){
  cfgState.cameras[cameraId].warp_points = null;
  if(picking.cameraId === cameraId) picking = { cameraId: null, points: [] };
  renderCameras();
}

function setWarpInputValue(cameraId){
  const input = document.getElementById(`warpInput_${cameraId}`);
  if(input) input.value = formatWarpPoints(cfgState.cameras[cameraId]?.warp_points);
}

function setWarpEnabledCheckbox(cameraId){
  const input = document.getElementById(`warpEnabled_${cameraId}`);
  if(input) input.checked = Boolean(cfgState.cameras[cameraId]?.warp_enabled);
}

function refreshCameraPreview(cameraId, corrected){
  const suffix = corrected ? "corrected" : "raw";
  const img = document.getElementById(`cameraImg_${suffix}_${cameraId}`);
  if(!img) return;
  img.src = `/api/camera/${encodeURIComponent(cameraId)}/stream?corrected=${corrected ? "true" : "false"}&t=${Date.now()}`;
}

function updateOverlayOnly(cameraId){
  const overlay = document.getElementById(`cameraOverlayWrap_${cameraId}`);
  if(overlay) overlay.innerHTML = overlaySvg(cameraId);

  const btn = document.getElementById(`pickBtn_${cameraId}`);
  if(btn){
    btn.textContent = picking.cameraId === cameraId
      ? `Кликни точку ${(picking.points.length / 2) + 1} из 4`
      : "Выбрать точки";
  }
}

function onRawPreviewClick(cameraId, event){
  if(picking.cameraId !== cameraId) return;

  const img = event.currentTarget.querySelector("img");
  if(!img || !img.naturalWidth || !img.naturalHeight) return;

  const rect = img.getBoundingClientRect();
  const x = Math.round((event.clientX - rect.left) * img.naturalWidth / rect.width);
  const y = Math.round((event.clientY - rect.top) * img.naturalHeight / rect.height);

  picking.points.push(x, y);

  if(picking.points.length === 8){
    cfgState.cameras[cameraId].warp_points = [...picking.points];
    cfgState.cameras[cameraId].warp_enabled = true;
    picking = { cameraId: null, points: [] };
    setWarpInputValue(cameraId);
    setWarpEnabledCheckbox(cameraId);
    updateOverlayOnly(cameraId);
    return;
  }

  // Важно: не вызываем renderCameras() после каждого клика.
  // Иначе браузер каждый раз пересоздаёт MJPEG-потоки,
  // Raspberry Pi быстро забивается открытыми stream-запросами и страница зависает.
  updateOverlayOnly(cameraId);
}

function overlaySvg(cameraId){
  const cam = cfgState.cameras[cameraId];
  const points = picking.cameraId === cameraId && picking.points.length ? picking.points : cam.warp_points;

  if(!Array.isArray(points) || points.length < 2) return "";

  const pairs = [];
  for(let i=0;i<points.length;i+=2) pairs.push([points[i], points[i+1]]);
  const poly = pairs.map(p => `${p[0]},${p[1]}`).join(" ");
  const circles = pairs.map((p, idx)=>`
    <circle cx="${p[0]}" cy="${p[1]}" r="8"></circle>
    <text x="${p[0] + 10}" y="${p[1] - 10}">${idx + 1}</text>
  `).join("");

  return `
    <svg class="cameraOverlay" viewBox="0 0 1280 720" preserveAspectRatio="none">
      <polyline points="${poly}" fill="none"></polyline>
      ${circles}
    </svg>
  `;
}

function cameraCard(cameraId){
  const cam = cfgState.cameras[cameraId];
  if(cam.autofocus_enabled === undefined) cam.autofocus_enabled = true;
  if(cam.focus_absolute === undefined) cam.focus_absolute = 512;
  if(cam.white_balance_auto === undefined) cam.white_balance_auto = true;
  if(cam.white_balance_temperature === undefined) cam.white_balance_temperature = 4;
  const pickText = picking.cameraId === cameraId
    ? `Кликни точку ${(picking.points.length / 2) + 1} из 4`
    : "Выбрать точки";

  const token = Date.now();

  return `
    <section class="cameraSettingsCard">
      <div class="cameraSettingsHead">
        <div>
          <div class="cameraSettingsTitle">${escapeHtml(cam.name || cameraId)}</div>
          <div class="cameraSettingsSub">${escapeHtml(cameraId)} · ${escapeHtml(cam.device || "")}</div>
        </div>
        <button class="btn btn--danger" onclick="deleteCamera('${escapeHtml(cameraId)}')">Удалить</button>
      </div>

      <div class="cameraSettingsGrid">
        <label>
          <span>Название</span>
          <input class="cfgInput" value="${escapeHtml(cam.name || "")}" onchange="changeCamera('${escapeHtml(cameraId)}', 'name', this.value)">
        </label>

        <label>
          <span>Устройство</span>
          <input class="cfgInput" value="${escapeHtml(cam.device || "")}" placeholder="/dev/video0" onchange="changeCamera('${escapeHtml(cameraId)}', 'device', this.value)">
        </label>
        
        <label class="cfgCheck cameraCheckInline">
          <input
            type="checkbox"
            ${cam.autofocus_enabled ? "checked" : ""}
            onchange="changeCamera('${escapeHtml(cameraId)}', 'autofocus_enabled', this.checked); renderCameras();"
          >
          <span>Автофокус</span>
        </label>
        
        <label>
          <span>Фокус 0–1023</span>
          <input
            class="cfgInput"
            type="number"
            min="0"
            max="1023"
            step="1"
            ${cam.autofocus_enabled ? "disabled" : ""}
            value="${cam.focus_absolute ?? ""}"
            onchange="changeCameraNumber('${escapeHtml(cameraId)}', 'focus_absolute', this.value)"
          >
        </label>
        
        <label class="cfgCheck cameraCheckInline">
          <input
            type="checkbox"
            ${cam.white_balance_auto ? "checked" : ""}
            onchange="changeCamera('${escapeHtml(cameraId)}', 'white_balance_auto', this.checked); renderCameras();"
          >
          <span>Автобаланс белого</span>
        </label>
        
        <label>
          <span>Баланс белого</span>
          <input
            class="cfgInput"
            type="number"
            min="1"
            max="10000"
            step="1"
            ${cam.white_balance_auto ? "disabled" : ""}
            value="${cam.white_balance_temperature ?? ""}"
            onchange="changeCameraNumber('${escapeHtml(cameraId)}', 'white_balance_temperature', this.value)"
          >
        </label>

        <label class="cfgCheck cameraCheckInline">
          <input type="checkbox" ${cam.flip_vertical ? "checked" : ""} onchange="changeCamera('${escapeHtml(cameraId)}', 'flip_vertical', this.checked)">
          <span>Поворот верх/низ</span>
        </label>

        <label class="cfgCheck cameraCheckInline">
          <input type="checkbox" ${cam.flip_horizontal ? "checked" : ""} onchange="changeCamera('${escapeHtml(cameraId)}', 'flip_horizontal', this.checked)">
          <span>Поворот влево/вправо</span>
        </label>

        <label class="cfgCheck cameraCheckInline">
          <input id="warpEnabled_${escapeHtml(cameraId)}" type="checkbox" ${cam.warp_enabled ? "checked" : ""} onchange="changeCamera('${escapeHtml(cameraId)}', 'warp_enabled', this.checked)">
          <span>Выравнивать перспективу</span>
        </label>

        <label class="cameraWarpText">
          <span>Точки</span>
          <input id="warpInput_${escapeHtml(cameraId)}" class="cfgInput" value="${escapeHtml(formatWarpPoints(cam.warp_points))}" placeholder="x1,y1 x2,y2 x3,y3 x4,y4" onchange="changeWarpText('${escapeHtml(cameraId)}', this.value)">
        </label>
      </div>

      <div class="cameraToolsRow">
        <button id="pickBtn_${escapeHtml(cameraId)}" class="btn btn--ghost" onclick="startPickPoints('${escapeHtml(cameraId)}')">${pickText}</button>
        <button class="btn btn--ghost" onclick="resetPoints('${escapeHtml(cameraId)}')">Сбросить точки</button>
        <span class="muted">Порядок: ЛВ → ПВ → ПН → ЛН</span>
      </div>

      <div class="cameraPreviewGrid">
        <div>
          <div class="cameraPreviewTitle">До коррекции</div>
          <div class="cameraPreviewBox ${picking.cameraId === cameraId ? "isPicking" : ""}" onclick="onRawPreviewClick('${escapeHtml(cameraId)}', event)">
            <img id="cameraImg_raw_${escapeHtml(cameraId)}" src="/api/camera/${encodeURIComponent(cameraId)}/stream?corrected=false&t=${token}" alt="До коррекции">
            <div id="cameraOverlayWrap_${escapeHtml(cameraId)}">${overlaySvg(cameraId)}</div>
          </div>
        </div>
        <div>
          <div class="cameraPreviewTitle">После коррекции</div>
          <div class="cameraPreviewBox">
            <img id="cameraImg_corrected_${escapeHtml(cameraId)}" src="/api/camera/${encodeURIComponent(cameraId)}/stream?corrected=true&t=${token}" alt="После коррекции">
          </div>
        </div>
      </div>
    </section>
  `;
}

function renderCameras(){
  const list = document.getElementById("camerasList");
  const ids = cameraIds();
  list.innerHTML = ids.length
    ? ids.map(cameraCard).join("")
    : `<div class="hint">Камер пока нет. Нажми «Добавить камеру».</div>`;
}

async function loadCfg(){
  try{
    cfgState = await api("/api/config");
    cfgState.racks = cfgState.racks || {};
    cfgState.cameras = cfgState.cameras || {};
    renderCameras();
    setConn(true);
  }catch(e){
    console.error(e);
    alert("Не удалось загрузить настройки камер: " + e.message);
    setConn(false);
  }
}

async function saveCameras(){
  try{
    for(const [cameraId, cam] of Object.entries(cfgState.cameras || {})){
      cam.name = String(cam.name || "").trim();
      cam.device = String(cam.device || "").trim();
      cam.autofocus_enabled = Boolean(cam.autofocus_enabled);
      cam.white_balance_auto = Boolean(cam.white_balance_auto);

      if(cam.focus_absolute != null && cam.focus_absolute !== ""){
        cam.focus_absolute = Number(cam.focus_absolute);
      }else{
        cam.focus_absolute = null;
      }

      if(cam.white_balance_temperature != null && cam.white_balance_temperature !== ""){
        cam.white_balance_temperature = Number(cam.white_balance_temperature);
      }else{
        cam.white_balance_temperature = null;
      }

      if(!cam.device){
        alert(`У камеры ${cameraId} не указано устройство`);
        return;
      }
    }

    await api("/api/config", "POST", cfgState);
    alert("Настройки камер сохранены");
    await loadCfg();
  }catch(e){
    console.error(e);
    alert("Не удалось сохранить настройки камер: " + e.message);
  }
}

document.getElementById("backBtn").addEventListener("click", ()=>{ window.location.href = "/"; });
document.getElementById("addCameraBtn").addEventListener("click", addCamera);
document.getElementById("saveCamerasBtn").addEventListener("click", saveCameras);

loadCfg();
