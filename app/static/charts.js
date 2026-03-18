async function api(path){
  const res = await fetch(path);
  if(!res.ok){
    throw new Error(await res.text());
  }
  return await res.json();
}

let moistureChart = null;
let tempChart = null;

function buildChart(canvasId, label, labels, data){
  const ctx = document.getElementById(canvasId).getContext("2d");
  return new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label,
        data
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true
    }
  });
}

async function loadCharts(){
  const rackId = document.getElementById("rackSelect").value;
  const hours = document.getElementById("hoursSelect").value;

  const data = await api(`/api/sensor-history/${rackId}?hours=${hours}`);
  const items = data.items || [];

  const labels = items.map(x => {
    const d = new Date(x.created_at);
    return d.toLocaleString("ru-RU");
  });

  const moisture = items.map(x => x.soil_moisture);
  const temp = items.map(x => x.soil_temperature);

  if(moistureChart) moistureChart.destroy();
  if(tempChart) tempChart.destroy();

  moistureChart = buildChart("moistureChart", "Влажность, %", labels, moisture);
  tempChart = buildChart("tempChart", "Температура, °C", labels, temp);
}

function initRacks(){
  const sel = document.getElementById("rackSelect");
  for(let i=1;i<=16;i++){
    const opt = document.createElement("option");
    opt.value = String(i);
    opt.textContent = `Полка ${i}`;
    sel.appendChild(opt);
  }
}

document.getElementById("backBtn").addEventListener("click", ()=>{
  window.location.href = "/";
});

document.getElementById("loadChartsBtn").addEventListener("click", loadCharts);

initRacks();
loadCharts();