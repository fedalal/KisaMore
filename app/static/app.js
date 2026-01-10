const DAYS = [
  {k:"mon", n:"Пн"},
  {k:"tue", n:"Вт"},
  {k:"wed", n:"Ср"},
  {k:"thu", n:"Чт"},
  {k:"fri", n:"Пт"},
  {k:"sat", n:"Сб"},
  {k:"sun", n:"Вс"},
];

// Должно соответствовать ALLOWED_GPIO_BCM в backend (app/hw_config.py)
const ALLOWED_GPIO_BCM = [4,5,6,12,13,16,17,18,19,20,21,22,23,24,25,26,27];

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

function badge(on, ico, labelOn, labelOff, until, tooltip, subtext){
  const suffix = (on && until) ? ` до ${until}` : "";
  const title = tooltip ? ` title="${tooltip.replaceAll('"','&quot;')}"` : "";
  const sub = subtext ? `<div class="badgeSub">${subtext}</div>` : "";
  return `<span class="badge ${on ? "badge--on":"badge--off"}"${title}>
    <span class="ico">${ico}</span>
    <span class="badgeMain">${on ? (labelOn + suffix) : labelOff}</span>
    ${sub}
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

function cardHtml(r){

    const lightToggle = toggleHtml(
        `t-light-${r.rack_id}`,
        r.light_mode === "manual",
        r.rack_id,
        "light"
      );

    const waterToggle = toggleHtml(
        `t-water-${r.rack_id}`,
        r.water_mode === "manual",
        r.rack_id,
        "water"
      );

    const lightIsSched = (r.light_mode === "schedule");
    const waterIsSched = (r.water_mode === "schedule");

    const lightUntil = (lightIsSched && r.light_on) ? r.light_until : null;
    const waterUntil = (waterIsSched && r.water_on) ? r.water_until : null;

    const lightTip = (lightIsSched && r.light_on && r.light_interval) ? `Интервал: ${r.light_interval}` : null;
    const waterTip = (waterIsSched && r.water_on && r.water_interval) ? `Интервал: ${r.water_interval}` : null;

    const lightNext = (lightIsSched && !r.light_on && r.light_next_on) ? `Следующее: ${r.light_next_on}` : null;
    const waterNext = (waterIsSched && !r.water_on && r.water_next_on) ? `Следующее: ${r.water_next_on}` : null;



  return `
  <div class="card">
    <div class="card__head">
      <div>
        <div class="card__title">Стеллаж ${r.rack_id}</div>
        <div class="card__meta">Режимы: 💡 ${modeRu(r.light_mode)} · 💧 ${modeRu(r.water_mode)}</div>
      </div>
      <button class="btn btn--ghost" onclick="openSchedule(${r.rack_id})">Расписание</button>
    </div>

    <div class="badges">
      ${badge(r.light_on, "💡", "Свет включен", "Свет выключен", lightUntil, lightTip, lightNext)}
      ${badge(r.water_on, "💧", "Полив идёт", "Полив остановлен", waterUntil, waterTip, waterNext)}
    </div>

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

/* ===== Schedule modal ===== */

function deepClone(x){ return JSON.parse(JSON.stringify(x)); }

function emptyChannel(){
  const c = {};
  for(const d of DAYS) c[d.k] = [];
  return c;
}

function normalizeSchedule(sch){
  const out = (sch && typeof sch === "object") ? sch : {};
  if(!out.light) out.light = emptyChannel();
  if(!out.water) out.water = emptyChannel();
  for(const d of DAYS){
    if(!Array.isArray(out.light[d.k])) out.light[d.k] = [];
    if(!Array.isArray(out.water[d.k])) out.water[d.k] = [];
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

function dayRow(dayKey, dayName, intervals){
  const items = intervals.map((it, idx) => `
    <div class="interval" data-day="${dayKey}" data-idx="${idx}">
      <input type="time" value="${it.start}" data-field="start"/>
      <span class="muted">—</span>
      <input type="time" value="${it.end}" data-field="end"/>
      <button class="iconBtn" title="Удалить" onclick="removeInterval('${dayKey}', ${idx})">🗑</button>
    </div>
  `).join("");

  return `
    <tr>
      <td class="day">
        <div class="dayHead">
          <span>${dayName}</span>
          <button class="iconBtn iconBtn--plus" title="Добавить интервал" onclick="addIntervalToDay('${dayKey}')">＋</button>
        </div>
      </td>
      <td>
        <div class="intervals" id="ints-${dayKey}">
          ${items || `<span class="muted">нет интервалов</span>`}
        </div>
      </td>
    </tr>
  `;
}

function renderScheduleTable(){
  const cont = document.getElementById("schedContainer");
  const channel = current.tab;
  const data = current.schedule[channel];

  const rows = DAYS.map(d => dayRow(d.k, d.n, data[d.k] || [])).join("");

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
      current.schedule[channel][day][idx][field] = e.target.value;
    });
  });
}

function removeInterval(dayKey, idx){
  const channel = current.tab;
  current.schedule[channel][dayKey].splice(idx, 1);
  renderScheduleTable();
}

// ✅ Новый способ добавления: кнопка "＋" у конкретного дня
function addIntervalToDay(dayKey){
  const channel = current.tab;
  current.schedule[channel][dayKey].push({start:"08:00", end:"20:00"});
  renderScheduleTable();
}

function validateSchedule(){
  const channel = current.tab;
  const data = current.schedule[channel];

  for(const d of DAYS){
    const arr = data[d.k] || [];
    for(const it of arr){
      if(!it.start || !it.end) return `Пустое время в ${d.n}`;
      if(it.end <= it.start) return `Интервал должен быть start < end (${d.n})`;
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

function relayOptions(selected){
  const opts = ['<option value="">—</option>']
    .concat(ALLOWED_GPIO_BCM.map(v => `<option value="${v}" ${String(v)===String(selected) ? "selected":""}>${v}</option>`));
  return opts.join("");
}

function relayNumOptions(selected){
  const opts = [];
  for(let i=1;i<=16;i++){
    opts.push(`<option value="${i}" ${String(i)===String(selected) ? "selected":""}>${i}</option>`);
  }
  return opts.join("");
}

function renderCfg(){
  if(!cfgState) return;

  document.getElementById("cfgRacksCount").value = cfgState.racks_count;

  const rows = [];
  rows.push(`<div class="cfgTable">
    <div class="cfgTableRow head">
      <div>Стеллаж</div><div>Реле света</div><div>Реле полива</div>
    </div>`);

  for(let i=1;i<=cfgState.racks_count;i++){
    const rk = String(i);
    if(!cfgState.racks[rk]) cfgState.racks[rk] = {light_relay:1, water_relay:2};
    const r = cfgState.racks[rk];
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
      </div>
    `);
  }
  rows.push(`</div>`);
  document.getElementById("cfgRacksTable").innerHTML = rows.join("");

  const r2g = cfgState.relay_to_gpio || {};
  const rows2 = [];
  rows2.push(`<div class="cfgTable">
    <div class="cfgTable2Row head">
      <div>Реле</div><div>GPIO (BCM)</div>
    </div>`);
  for(let i=1;i<=16;i++){
    const key = String(i);
    const val = (key in r2g) ? r2g[key] : "";
    rows2.push(`
      <div class="cfgTable2Row">
        <div class="cfgCellLabel">${i}</div>
        <div>
          <select class="cfgSelect" onchange="cfgRelayGpioChange(${i}, this.value)">
            ${relayOptions(val)}
          </select>
        </div>
      </div>
    `);
  }
  rows2.push(`</div>`);
  document.getElementById("cfgRelaysTable").innerHTML = rows2.join("");
}

function cfgRackRelayChange(rackId, field, value){
  const rk = String(rackId);
  cfgState.racks[rk][field] = Number(value);
}

function cfgRelayGpioChange(relayId, value){
  const k = String(relayId);
  if(value === "" || value === null){
    delete cfgState.relay_to_gpio[k];
  }else{
    cfgState.relay_to_gpio[k] = Number(value);
  }
}

function cfgRacksCountChange(value){
  let n = Number(value);
  if(!Number.isFinite(n)) n = 1;
  n = Math.max(1, Math.min(16, n));
  cfgState.racks_count = n;

  for(let i=1;i<=n;i++){
    const k = String(i);
    if(!cfgState.racks[k]) cfgState.racks[k] = {light_relay:1, water_relay:2};
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
    cfgState.relay_to_gpio = cfgState.relay_to_gpio || {};
    cfgState.racks = cfgState.racks || {};
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
    for(const k of Object.keys(cfgState.racks)){
      const r = cfgState.racks[k];
      if(r.light_relay < 1 || r.light_relay > 16 || r.water_relay < 1 || r.water_relay > 16){
        alert("Номер реле должен быть 1..16");
        return;
      }
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
document.getElementById("refreshBtn").addEventListener("click", refresh);

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
document.getElementById("cfgReload").addEventListener("click", loadCfg);
document.getElementById("cfgSave").addEventListener("click", saveCfg);
document.getElementById("cfgRacksCount").addEventListener("change", (e)=>cfgRacksCountChange(e.target.value));

refresh();
startAutoRefresh();
