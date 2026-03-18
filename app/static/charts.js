async function api(path){
  const res = await fetch(path);
  if(!res.ok){
    throw new Error(await res.text());
  }
  return await res.json();
}

let moistureChart = null;
let tempChart = null;
let autoTimer = null;

function getColor(i){
  const colors = [
    "#3b82f6","#22c55e","#ef4444","#f59e0b",
    "#8b5cf6","#06b6d4","#84cc16","#ec4899"
  ];
  return colors[i % colors.length];
}

function buildChart(canvasId, datasets, labels){
  const ctx = document.getElementById(canvasId).getContext("2d");

  return new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: true
        }
      },
      elements: {
        point: {
          radius: 0
        }
      }
    }
  });
}

async function loadCharts(){
  const rackId = document.getElementById("rackSelect").value;
  const hours = document.getElementById("hoursSelect").value;

  let url = `/api/sensor-history?hours=${hours}`;
  if(rackId !== "all"){
    url += `&rack_id=${rackId}`;
  }

  const data = await api(url);
  const items = data.items || {};

  if(moistureChart) moistureChart.destroy();
  if(tempChart) tempChart.destroy();

  let labels = [];
  const moistureDatasets = [];
  const tempDatasets = [];

  let i = 0;

  for(const [rid, arr] of Object.entries(items)){
    const l = arr.map(x => {
      const d = new Date(x.created_at);
      return d.toLocaleTimeString("ru-RU");
    });

    if(i === 0){
      labels = l;
    }

    const moisture = arr.map(x => x.soil_moisture);
    const temp = arr.map(x => x.soil_temperature);

    const color = getColor(i++);

    moistureDatasets.push({
      label: `Полка ${rid}`,
      data: moisture,
      borderColor: color,
      tension: 0.2,
      fill: false
    });

    tempDatasets.push({
      label: `Полка ${rid}`,
      data: temp,
      borderColor: color,
      tension: 0.2,
      fill: false
    });
  }

  moistureChart = buildChart("moistureChart", moistureDatasets, labels);
  tempChart = buildChart("tempChart", tempDatasets, labels);

  // подпись
  const title = (rackId === "all")
    ? "Все полки"
    : `Полка ${rackId}`;

  document.getElementById("moistureMeta").textContent = title;
  document.getElementById("tempMeta").textContent = title;
}

async function initRacks(){
  const sel = document.getElementById("rackSelect");

  // важно: не затираем "Все полки"
  sel.innerHTML = `<option value="all">Все полки</option>`;

  const cfg = await api("/api/config");
  const count = cfg.racks_count || 0;

  for(let i = 1; i <= count; i++){
    const opt = document.createElement("option");
    opt.value = String(i);
    opt.textContent = `Полка ${i}`;
    sel.appendChild(opt);
  }
}

function startAutoRefresh(){
  if(autoTimer) clearInterval(autoTimer);

  autoTimer = setInterval(()=>{
    loadCharts();
  }, 10000); // каждые 10 сек
}

function stopAutoRefresh(){
  if(autoTimer){
    clearInterval(autoTimer);
    autoTimer = null;
  }
}

document.getElementById("backBtn").addEventListener("click", ()=>{
  window.location.href = "/";
});

document.getElementById("loadChartsBtn").addEventListener("click", loadCharts);

document.getElementById("autoRefresh").addEventListener("change", (e)=>{
  if(e.target.checked){
    startAutoRefresh();
  }else{
    stopAutoRefresh();
  }
});

window.addEventListener("beforeunload", ()=>{
  stopAutoRefresh();
});

async function initPage(){
  await initRacks();
  await loadCharts();

  if(document.getElementById("autoRefresh").checked){
    startAutoRefresh();
  }
}

initPage();