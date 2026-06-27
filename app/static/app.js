const DAYS = [
  {k:"mon", n:"Пн"},
  {k:"tue", n:"Вт"},
  {k:"wed", n:"Ср"},
  {k:"thu", n:"Чт"},
  {k:"fri", n:"Пт"},
  {k:"sat", n:"Сб"},
  {k:"sun", n:"Вс"},
];

let current = { rackId: null, tab: "light", schedule: null };
let refreshTimer = null;
let isBusy = false;

let cfgState = null;

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

function modeRu(mode){
  return mode === "manual" ? "Вручную" : "По расписанию";
}

function untilNextLine(on, untilStr, nextStr){
  if(on && untilStr) return `<div class="untilNext">до <span class="code">${untilStr}</span></div>`;
  if(!on && nextStr) return `<div class="untilNext">след. <span class="code">${nextStr}</span></div>`;
  return `<div class="untilNext muted">нет расписания</div>`;
}

function validateUniqueRelaysWithHighlight(){
  document.querySelectorAll(".cfgSelect").forEach(el=>{
    el.classList.remove("cfgError");
  });

  const used = {};
  const conflicts = {};

  for(const rackId of Object.keys(cfgState.racks)){
    const r = cfgState.racks[rackId];

    for(const [field, label] of [
      ["light_relay", "Свет"],
      ["water_relay", "Полив"]
    ]){
      const relay = r[field];
      const key = String(relay);

      if(!used[key]) used[key] = [];
      used[key].push({ rackId, label });
    }
  }

  for(const relay of Object.keys(used)){
    if(used[relay].length > 1){
      conflicts[relay] = used[relay];
      used[relay].forEach(({ rackId, label })=>{
        const sel = document.querySelector(
          `.cfgSelect[onchange*="(${rackId}, '${label === "Свет" ? "light_relay" : "water_relay"}"]`
        );
        if(sel) sel.classList.add("cfgError");
      });
    }
  }

  if(Object.keys(conflicts).length){
    let msg = "Ошибка: одно и то же реле назначено нескольким устройствам:\n\n";
    for(const r of Object.keys(conflicts)){
      msg += `Реле ${r}: ` + conflicts[r]
        .map(x=>`Стеллаж ${x.rackId} — ${x.label}`)
        .join(", ") + "\n";
    }
    alert(msg);
    return false;
  }

  return true;
}

function soilInfoHtml(r){
  const hasMoisture = r.soil_moisture !== null && r.soil_moisture !== undefined;
  const hasTemp = r.soil_temperature !== null && r.soil_temperature !== undefined;

  if(!hasMoisture && !hasTemp){
    return `<div class="soilLine muted">🌱 Датчик почвы: нет данных</div>`;
  }

  const moistureText = hasMoisture
    ? `💧 Влажность: <b>${Number(r.soil_moisture).toFixed(1)}%</b>`
    : `💧 Влажность: <b>—</b>`;

  const tempText = hasTemp
    ? `🌡 Темп.: <b>${Number(r.soil_temperature).toFixed(1)}°C</b>`
    : `🌡 Темп.: <b>—</b>`;

  return `
    <div class="soilLine">
      <span class="soilBadge">${moistureText}</span>
      <span class="soilBadge">${tempText}</span>
    </div>
  `;
}


function badge(kind, ico, on, mode, untilStr, nextStr){
  let text;

  if(mode === "schedule"){
    if(on && untilStr){
      text = `${kind} включен до ${untilStr}`;
    } else if(!on && nextStr){
      text = `${kind} выключен · след. ${nextStr}`;
    } else {
      text = on ? `${kind} включен` : `${kind} выключен`;
    }
  } else {
    // manual
    text = on ? `${kind} включен` : `${kind} выключен`;
  }

  return `<span class="badge ${on ? "badge--on":"badge--off"}">
    <span class="ico">${ico}</span>
    ${text}
  </span>`;
}


function toggleHtml(id, isManual, rackId, channel){
  return `
    <label class="toggle" title="Переключить режим">
      <span class="tlabel ${!isManual ? "active":""}">По расписанию</span>
      <input id="${id}" type="checkbox"
             ${isManual ? "checked":""}
             onchange="onToggleMode(${rackId}, '${channel}', this.checked)">
      <span class="switch"><span class="knob"></span></span>
      <span class="tlabel ${isManual ? "active":""}">Вручную</span>
    </label>
  `;
}

function cameraButtonHtml(r){
  if(!r.camera_device) return "";

  return `
    <button
      class="btn btn--ghost btn--eye"
      title="Открыть камеру ${escapeHtml(r.camera_device)}"
      onclick="openCameraWindow(${r.rack_id}, '${escapeHtml(r.camera_device)}')"
      aria-label="Открыть камеру"
    >
      📷
    </button>
  `;
}


function cardHtml(r){
  const lightToggle = toggleHtml(`t-light-${r.rack_id}`, r.light_mode === "manual", r.rack_id, "light");
  const waterToggle = toggleHtml(`t-water-${r.rack_id}`, r.water_mode === "manual", r.rack_id, "water");

  return `
  <div class="card">
    <div class="card__head">
      <div>
        <div class="card__title">Стеллаж ${r.rack_id}</div>
        <div class="card__meta">Режимы: 💡 ${modeRu(r.light_mode)} · 💧 ${modeRu(r.water_mode)}</div>
      </div>
       ${cameraButtonHtml(r)}
      <button class="btn btn--ghost" onclick="openSchedule(${r.rack_id})">Расписание</button>
    </div>

    <div class="badges">
      ${badge("Свет", "💡", r.light_on, r.light_mode, r.light_until, r.light_next)}
      ${badge("Полив", "💧", r.water_on, r.water_mode, r.water_until, r.water_next)}
    </div>

    ${soilInfoHtml(r)}

    <div class="controls">
      <div class="controlRow">
        <div class="left">
          <div class="stack">
            <div class="label">💡 Свет</div>
            <div class="sub">Режим: ${lightToggle}</div>
          </div>
        </div>
        <div class="btns">
          <button class="btn ${r.light_on ? "btn--active" : ""}"
                  onclick="setManual(${r.rack_id}, 'light', true)">
            Вкл
          </button>
          <button class="btn ${!r.light_on ? "btn--active" : ""}"
                  onclick="setManual(${r.rack_id}, 'light', false)">
            Выкл
          </button>
        </div>
      </div>

      <div class="controlRow">
        <div class="left">
          <div class="stack">
            <div class="label">💧 Полив</div>
            <div class="sub">Режим: ${waterToggle}</div>
          </div>
        </div>
        <div class="btns">
          <button class="btn ${r.water_on ? "btn--active" : ""}"
                  onclick="setManual(${r.rack_id}, 'water', true)">
            Вкл
          </button>
          <button class="btn ${!r.water_on ? "btn--active" : ""}"
                  onclick="setManual(${r.rack_id}, 'water', false)">
            Выкл
          </button>
        </div>
      </div>
    </div>
  </div>`;
}

async function refresh(){
  try{
    const data = await api("/api/state");
    document.getElementById("cards").innerHTML = data.map(cardHtml).join("");
    setConn(true);
  }catch(e){
    console.error(e);
    setConn(false);
  }
}

function startAutoRefresh(){
  if(refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(()=>{ if(!isBusy) refresh(); }, 2000);
}

function setConn(ok){
  const el = document.getElementById("conn");
  el.textContent = ok ? "🟢 онлайн" : "🔴 нет связи";
}

async function shutdownPi(){
  const ok = confirm("Вы действительно хотите выключить Raspberry Pi?\nПодключение будет потеряно.");
  if(!ok) return;

  try{
    isBusy = true;

    // если у тебя эндпоинт другой — поменяй путь
    await api("/api/system/shutdown", "POST", {});

    alert("Raspberry Pi выключается…");
  }catch(e){
    console.error(e);
    alert("Не удалось выключить Raspberry Pi: " + (e?.message || e));
  }finally{
    isBusy = false;
  }
}


async function setManual(rackId, channel, on){
  try{
    isBusy = true;
    await api(`/api/rack/${rackId}/${channel}/manual`, "POST", {on});
  } finally {
    isBusy = false;
  }
  await refresh();
}

async function setMode(rackId, channel, mode){
  await api(`/api/rack/${rackId}/${channel}/mode`, "POST", {mode});
}

async function onToggleMode(rackId, channel, checked){
  try{
    isBusy = true;
    await setMode(rackId, channel, checked ? "manual" : "schedule");
  } finally {
    isBusy = false;
  }
  await refresh();
}

/* ===== Camera window ===== */

function openCameraWindow(rackId, device){
  const win = document.getElementById("cameraWindow");
  const img = document.getElementById("cameraImg");
  const title = document.getElementById("cameraTitle");
  const sub = document.getElementById("cameraSub");

  if(!win || !img) return;

  title.textContent = `Камера · Стеллаж ${rackId}`;
  sub.textContent = device || "";

  img.src = `/api/rack/${rackId}/camera/stream?t=${Date.now()}`;

  win.classList.add("show");
  win.setAttribute("aria-hidden", "false");
}

function closeCameraWindow(){
  const win = document.getElementById("cameraWindow");
  const img = document.getElementById("cameraImg");

  if(img) img.removeAttribute("src");

  if(win){
    win.classList.remove("show");
    win.setAttribute("aria-hidden", "true");
  }
}

function initCameraWindowDrag(){
  const win = document.getElementById("cameraWindow");
  const handle = document.getElementById("cameraDragHandle");
  const closeBtn = document.getElementById("cameraClose");

  if(!win || !handle) return;

  let dragging = false;
  let startX = 0;
  let startY = 0;
  let startLeft = 0;
  let startTop = 0;

  handle.addEventListener("mousedown", (e)=>{
    if(e.target.closest("button")) return;

    dragging = true;

    const rect = win.getBoundingClientRect();

    startX = e.clientX;
    startY = e.clientY;
    startLeft = rect.left;
    startTop = rect.top;

    win.style.left = `${startLeft}px`;
    win.style.top = `${startTop}px`;
    win.style.right = "auto";
    win.style.bottom = "auto";

    document.body.classList.add("draggingCamera");
    e.preventDefault();
  });

  window.addEventListener("mousemove", (e)=>{
    if(!dragging) return;

    const newLeft = Math.max(
      0,
      Math.min(window.innerWidth - win.offsetWidth, startLeft + e.clientX - startX)
    );

    const newTop = Math.max(
      0,
      Math.min(window.innerHeight - win.offsetHeight, startTop + e.clientY - startY)
    );

    win.style.left = `${newLeft}px`;
    win.style.top = `${newTop}px`;
  });

  window.addEventListener("mouseup", ()=>{
    if(!dragging) return;

    dragging = false;
    document.body.classList.remove("draggingCamera");
  });

  if(closeBtn){
    closeBtn.addEventListener("click", closeCameraWindow);
  }
}

/* ===== Schedule modal ===== */

function deepClone(x){ return JSON.parse(JSON.stringify(x)); }

function emptyChannel(){
  const c = {};
  for(const d of DAYS) c[d.k] = [];
  return c;
}

function pad2(n){
  return String(n).padStart(2, "0");
}

function timeParts(value){
  const parts = String(value || "").split(":");
  const h = Number(parts[0] || 0);
  const m = Number(parts[1] || 0);
  const s = Number(parts[2] || 0);
  return {h, m, s};
}

function timeToSeconds(value){
  const {h, m, s} = timeParts(value);
  if(!Number.isFinite(h) || !Number.isFinite(m) || !Number.isFinite(s)) return null;
  return h * 3600 + m * 60 + s;
}

function formatTimeValue(value, withSeconds){
  const {h, m, s} = timeParts(value);
  if(withSeconds){
    return `${pad2(h)}:${pad2(m)}:${pad2(s)}`;
  }
  return `${pad2(h)}:${pad2(m)}`;
}

function normalizeSchedule(sch){
  const out = (sch && typeof sch === "object") ? sch : {};
  if(!out.light) out.light = emptyChannel();
  if(!out.water) out.water = emptyChannel();
  for(const d of DAYS){
    if(!Array.isArray(out.light[d.k])) out.light[d.k] = [];
    if(!Array.isArray(out.water[d.k])) out.water[d.k] = [];

    out.light[d.k] = out.light[d.k].map(it => ({
      start: formatTimeValue(it.start, false),
      end: formatTimeValue(it.end, false),
    }));

    out.water[d.k] = out.water[d.k].map(it => ({
      start: formatTimeValue(it.start, true),
      end: formatTimeValue(it.end, true),
    }));
  }
  return out;
}

function openModal(show){
  const m = document.getElementById("modal");
  if(show){
    m.classList.add("show");
    m.setAttribute("aria-hidden","false");
  }else{
    m.classList.remove("show");
    m.setAttribute("aria-hidden","true");
  }
}

function setActiveTab(tab){
  current.tab = tab;
  document.querySelectorAll(".tab").forEach(b=>{
    b.classList.toggle("tab--active", b.dataset.tab === tab);
  });
  renderScheduleTable();
}

function dayRow(dayKey, dayName, intervals, channel){
  const withSeconds = channel === "water";
  const step = withSeconds ? 1 : 60;

  const items = intervals.map((it, idx) => `
    <div class="interval" data-day="${dayKey}" data-idx="${idx}">
      <input type="time" step="${step}" value="${formatTimeValue(it.start, withSeconds)}" data-field="start"/>
      <span class="muted">—</span>
      <input type="time" step="${step}" value="${formatTimeValue(it.end, withSeconds)}" data-field="end"/>
      <button class="iconBtn" title="Удалить" onclick="removeInterval('${dayKey}', ${idx})">🗑</button>
    </div>
  `).join("");

  return `
    <tr>
      <td class="day">
        <div class="dayHead">
          <span>${dayName}</span>
          <button class="iconBtn" title="Добавить интервал" onclick="addIntervalForDay('${dayKey}')">＋</button>
        </div>
      </td>
      <td>
        <div class="intervals" id="ints-${dayKey}">${items || `<span class="muted">нет интервалов</span>`}</div>
      </td>
    </tr>
  `;
}

function renderScheduleTable(){
  const cont = document.getElementById("schedContainer");
  const channel = current.tab;
  const data = current.schedule[channel];

  const rows = DAYS.map(d => dayRow(d.k, d.n, data[d.k] || [], channel)).join("");

  cont.innerHTML = `
    <table class="table">
      <thead>
        <tr><th>День</th><th>Интервалы</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;

  cont.querySelectorAll('input[type="time"]').forEach(inp=>{
    inp.addEventListener("change", (e)=>{
      const wrap = e.target.closest(".interval");
      const day = wrap.dataset.day;
      const idx = Number(wrap.dataset.idx);
      const field = e.target.dataset.field;
      current.schedule[channel][day][idx][field] = formatTimeValue(e.target.value, channel === "water");
    });
  });
}

function removeInterval(dayKey, idx){
  const channel = current.tab;
  current.schedule[channel][dayKey].splice(idx, 1);
  renderScheduleTable();
}

function addIntervalForDay(dayKey){
  const channel = current.tab;
  if(channel === "water"){
    current.schedule[channel][dayKey].push({start:"08:00:00", end:"08:01:00"});
  }else{
    current.schedule[channel][dayKey].push({start:"08:00", end:"20:00"});
  }
  renderScheduleTable();
}

function validateSchedule(){
  const channel = current.tab;
  const data = current.schedule[channel];

  for(const d of DAYS){
    const arr = data[d.k] || [];
    for(const it of arr){
      if(!it.start || !it.end) return `Пустое время в ${d.n}`;
      const startSec = timeToSeconds(it.start);
      const endSec = timeToSeconds(it.end);
      if(startSec === null || endSec === null) return `Неверное время в ${d.n}`;
      if(endSec <= startSec) return `Интервал должен быть start < end (${d.n})`;
    }
  }
  return null;
}

async function openSchedule(rackId){
  current.rackId = rackId;
  document.getElementById("modalSub").textContent = `Стеллаж ${rackId}`;

  const sch = await api(`/api/rack/${rackId}/schedule`);
  current.schedule = normalizeSchedule(deepClone(sch));

  setActiveTab("light");
  openModal(true);
}

async function saveSchedule(){
  const err = validateSchedule();
  if(err){ alert(err); return; }
  const payload = normalizeSchedule(current.schedule);
  await api(`/api/rack/${current.rackId}/schedule`, "POST", payload);
  openModal(false);
}

/* ===== Config modal ===== */

function openCfgModal(show){
  const m = document.getElementById("cfgModal");
  if(show){
    m.classList.add("show");
    m.setAttribute("aria-hidden","false");
  }else{
    m.classList.remove("show");
    m.setAttribute("aria-hidden","true");
  }
}

function relayNumOptions(selected){
  const opts = [];
  for(let i=1;i<=16;i++){
    opts.push(`<option value="${i}" ${String(i)===String(selected) ? "selected":""}>${i}</option>`);
  }
  return opts.join("");
}

function escapeHtml(value){
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderCfg(){
  if(!cfgState) return;

  document.getElementById("cfgRacksCount").value = cfgState.racks_count;

  const rows = [];
  rows.push(`
    <div class="cfgTable">
      <div class="cfgTableRow head">
        <div class="cfgCellLabel">Стеллаж</div>
        <div>Реле света</div>
        <div>Реле полива</div>
        <div>Адрес датчика</div>
        <div>Web камера</div>
      </div>
  `);

  for(let i=1; i<=cfgState.racks_count; i++){
    const rk = String(i);

    if(!cfgState.racks[rk]){
      cfgState.racks[rk] = {
        light_relay: 1,
        water_relay: 2,
        sensor_slave_id: i,
        camera_device: `/dev/video${i - 1}`
      };
    }

    const r = cfgState.racks[rk];
    if(r.camera_device === undefined) r.camera_device = `/dev/video${i - 1}`;

    rows.push(`
      <div class="cfgTableRow">
        <div class="cfgCellLabel">${i}</div>

        <div>
          <select class="cfgSelect" onchange="cfgRackRelayChange(${i}, 'light_relay', this.value)">
            ${relayNumOptions(r.light_relay)}
          </select>
        </div>

        <div>
          <select class="cfgSelect" onchange="cfgRackRelayChange(${i}, 'water_relay', this.value)">
            ${relayNumOptions(r.water_relay)}
          </select>
        </div>

        <div>
          <input
            class="cfgInput"
            type="number"
            min="1"
            max="247"
            placeholder="нет"
            value="${r.sensor_slave_id ?? ""}"
            onchange="cfgRackSensorChange(${i}, this.value)"
          />
        </div>
        
        <div>
          <input
            class="cfgInput"
            type="text"
            placeholder="/dev/video"
            value="${escapeHtml(r.camera_device ?? "")}"
            onchange="cfgRackCameraChange(${i}, this.value)"
          />
        </div>

      </div>
    `);
  }

  rows.push(`</div>`);
  document.getElementById("cfgRacksTable").innerHTML = rows.join("");
}

function cfgRackRelayChange(rackId, field, value){
  const rk = String(rackId);
  cfgState.racks[rk][field] = Number(value);
}

function cfgRackSensorChange(rackId, value){
  const rk = String(rackId);
  const v = String(value).trim();

  if(v === ""){
    cfgState.racks[rk].sensor_slave_id = null;
    return;
  }

  cfgState.racks[rk].sensor_slave_id = Number(v);
}

function cfgRackCameraChange(rackId, value){
  const rk = String(rackId);
  const v = String(value).trim();
  cfgState.racks[rk].camera_device = v || null;
}

function cfgRacksCountChange(value){
  let n = Number(value);
  if(!Number.isFinite(n)) n = 1;
  n = Math.max(1, Math.min(16, n));
  cfgState.racks_count = n;

  for(let i=1;i<=n;i++){
    const k = String(i);
    if(!cfgState.racks[k]){
      cfgState.racks[k] = {
        light_relay:1,
        water_relay:2,
        sensor_slave_id:i,
        camera_device:`/dev/video${i - 1}`
      };
    }
  }

  Object.keys(cfgState.racks).forEach(k=>{
    if(Number(k) > n) delete cfgState.racks[k];
  });

  renderCfg();
}

async function loadCfg(){
  try{
    isBusy = true;
    cfgState = await api("/api/config");
    cfgState.racks = cfgState.racks || {};

    for(let i=1;i<=cfgState.racks_count;i++){
      const k = String(i);
      if(!cfgState.racks[k]){
        cfgState.racks[k] = {
          light_relay:1,
          water_relay:2,
          sensor_slave_id:i,
          camera_device:`/dev/video${i - 1}`
        };
      }
    }

    renderCfg();
    setConn(true);
  }catch(e){
    console.error(e);
    alert("Не удалось загрузить настройки: " + e.message);
    setConn(false);
  } finally {
    isBusy = false;
  }
}

async function saveCfg(){
  try{
    isBusy = true;

    document.querySelectorAll(".cfgSelect.cfgError, .cfgInput.cfgError").forEach(el => {
      el.classList.remove("cfgError");
    });

    // 1) Проверка диапазона реле
    for(const k of Object.keys(cfgState.racks)){
      const r = cfgState.racks[k];

      if(r.light_relay < 1 || r.light_relay > 16 || r.water_relay < 1 || r.water_relay > 16){
        alert("Номер реле должен быть 1..16");

        const rackId = Number(k);
        const selL = document.querySelector(`.cfgSelect[onchange="cfgRackRelayChange(${rackId}, 'light_relay', this.value)"]`);
        const selW = document.querySelector(`.cfgSelect[onchange="cfgRackRelayChange(${rackId}, 'water_relay', this.value)"]`);

        if(selL) selL.classList.add("cfgError");
        if(selW) selW.classList.add("cfgError");
        return;
      }
    }

    // 2) Проверка диапазона адресов датчиков
    for(const k of Object.keys(cfgState.racks)){
      const r = cfgState.racks[k];
      const rackId = Number(k);

      if(r.sensor_slave_id != null && r.sensor_slave_id !== ""){
        if(r.sensor_slave_id < 1 || r.sensor_slave_id > 247){
          alert(`Адрес датчика у стеллажа ${rackId} должен быть в диапазоне 1..247`);

          const inp = document.querySelector(`.cfgInput[onchange="cfgRackSensorChange(${rackId}, this.value)"]`);
          if(inp) inp.classList.add("cfgError");
          return;
        }
      }
    }

    // 3) Проверка уникальности реле
    const used = new Map();

    const addUse = (relayNum, rackId, field, label) => {
      if(!used.has(relayNum)) used.set(relayNum, []);
      used.get(relayNum).push({rackId, field, label});
    };

    for(const k of Object.keys(cfgState.racks)){
      const rackId = Number(k);
      const r = cfgState.racks[k];

      addUse(r.light_relay, rackId, "light_relay", `Стеллаж ${rackId} — Свет`);
      addUse(r.water_relay, rackId, "water_relay", `Стеллаж ${rackId} — Полив`);
    }

    const dups = [];
    for(const [relayNum, items] of used.entries()){
      if(items.length > 1){
        for(const it of items){
          const sel = document.querySelector(`.cfgSelect[onchange="cfgRackRelayChange(${it.rackId}, '${it.field}', this.value)"]`);
          if(sel) sel.classList.add("cfgError");
        }
        dups.push(`Реле ${relayNum}: ${items.map(x => x.label).join(", ")}`);
      }
    }

    if(dups.length){
      alert("Ошибка: одно и то же реле назначено нескольким устройствам:\n\n" + dups.join("\n"));
      return;
    }

    // 4) Проверка уникальности адресов датчиков
    const sensorUsed = new Map();
    const sensorDups = [];

    for(const k of Object.keys(cfgState.racks)){
      const rackId = Number(k);
      const r = cfgState.racks[k];
      const sid = r.sensor_slave_id;

      if(sid == null || sid === "") continue;

      if(!sensorUsed.has(sid)) sensorUsed.set(sid, []);
      sensorUsed.get(sid).push(rackId);
    }

    for(const [sid, rackIds] of sensorUsed.entries()){
      if(rackIds.length > 1){
        rackIds.forEach(rackId => {
          const inp = document.querySelector(`.cfgInput[onchange="cfgRackSensorChange(${rackId}, this.value)"]`);
          if(inp) inp.classList.add("cfgError");
        });
        sensorDups.push(`Адрес ${sid}: ${rackIds.map(id => `Стеллаж ${id}`).join(", ")}`);
      }
    }

    if(sensorDups.length){
      alert("Ошибка: один и тот же адрес датчика назначен нескольким стеллажам:\n\n" + sensorDups.join("\n"));
      return;
    }

    await api("/api/config", "POST", cfgState);
    openCfgModal(false);
    await refresh();

  }catch(e){
    console.error(e);
    alert("Не удалось сохранить настройки: " + e.message);
  } finally {
    isBusy = false;
  }
}

/* ===== Wire up ===== */
//document.getElementById("refreshBtn").addEventListener("click", refresh);

document.getElementById("chartsBtn").addEventListener("click", ()=>{
  window.location.href = "/charts";
});

const shutdownBtn = document.getElementById("shutdownBtn");
if(shutdownBtn){
  shutdownBtn.addEventListener("click", shutdownPi);
}

// schedule modal
document.getElementById("modalClose").addEventListener("click", ()=>openModal(false));
document.getElementById("modalX").addEventListener("click", ()=>openModal(false));
document.getElementById("saveSchedule").addEventListener("click", saveSchedule);
document.querySelectorAll(".tab").forEach(b=> b.addEventListener("click", ()=>setActiveTab(b.dataset.tab)));

// config modal
document.getElementById("settingsBtn").addEventListener("click", async ()=>{
  await loadCfg();
  openCfgModal(true);
});
document.getElementById("cfgClose").addEventListener("click", ()=>openCfgModal(false));
document.getElementById("cfgX").addEventListener("click", ()=>openCfgModal(false));
document.getElementById("cfgCancel").addEventListener("click", ()=>openCfgModal(false));
document.getElementById("cfgSave").addEventListener("click", saveCfg);
document.getElementById("cfgRacksCount").addEventListener("change", (e)=>cfgRacksCountChange(e.target.value));

initCameraWindowDrag();
refresh();
startAutoRefresh();
