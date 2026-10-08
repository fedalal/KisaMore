// Main rack page: camera access is snapshot-only. Multiple cameras can be
// assigned to one rack; the first item returned by /api/rack/{id}/cameras is
// the primary camera and preserves the old behaviour.

let snapshotRackId = null;
let snapshotCameraId = null;
let snapshotCameras = [];

cameraButtonHtml = function(r){
  const count = Array.isArray(r.camera_ids) ? r.camera_ids.length : (r.camera_device ? 1 : 0);
  if(!count) return "";

  return `
    <button
      class="btn btn--ghost btn--eye"
      title="Получить кадр с камеры"
      onclick="openCameraWindow(${r.rack_id}, '${escapeHtml(r.camera_device || "")}')"
      aria-label="Получить кадр с камеры"
    > Кадр${count > 1 ? ` (${count})` : ""}
      <svg class="cameraIcon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7.5 7.25 8.8 5.5h6.4l1.3 1.75h2.25c1.1 0 2 .9 2 2v8.25c0 1.1-.9 2-2 2H5.25c-1.1 0-2-.9-2-2V9.25c0-1.1.9-2 2-2H7.5Z"></path>
        <circle cx="12" cy="13" r="4"></circle>
        <circle cx="18" cy="10" r="1"></circle>
      </svg>
    </button>
  `;
};

function currentSnapshotCamera(){
  return snapshotCameras.find(item => item.camera_id === snapshotCameraId) || snapshotCameras[0] || null;
}

function renderSnapshotCameraSelector(){
  const sub = document.getElementById("cameraSub");
  if(!sub) return;

  if(snapshotCameras.length <= 1){
    const current = currentSnapshotCamera();
    sub.textContent = current ? (current.camera_name || current.camera_device || "") : "";
    return;
  }

  const options = snapshotCameras.map(item => {
    const label = (item.primary ? "Основная · " : "") + (item.camera_name || item.camera_id);
    return `<option value="${escapeHtml(item.camera_id)}" ${item.camera_id === snapshotCameraId ? "selected" : ""}>${escapeHtml(label)}</option>`;
  }).join("");

  sub.innerHTML = `
    <label style="display:flex;align-items:center;gap:8px">
      <span>Камера:</span>
      <select id="rackCameraSelect" class="cfgSelect" style="min-width:190px">${options}</select>
    </label>
  `;

  const select = document.getElementById("rackCameraSelect");
  if(select){
    select.addEventListener("change", () => {
      snapshotCameraId = select.value;
      refreshRackCameraFrame();
    });
  }
}

async function loadRackCameras(rackId){
  const response = await fetch(`/api/rack/${rackId}/cameras`, {cache:"no-store"});
  if(!response.ok) throw new Error(await response.text() || response.statusText);
  const rows = await response.json();
  snapshotCameras = Array.isArray(rows) ? rows : [];
  snapshotCameraId = snapshotCameras[0]?.camera_id || null;
  renderSnapshotCameraSelector();
}

function refreshRackCameraFrame(){
  const img = document.getElementById("cameraImg");
  if(!img || snapshotRackId == null) return;

  img.alt = "Получение кадра…";
  if(snapshotCameraId){
    img.src = `/api/rack/${snapshotRackId}/cameras/${encodeURIComponent(snapshotCameraId)}/frame?t=${Date.now()}`;
  }else{
    img.src = `/api/rack/${snapshotRackId}/camera/frame?t=${Date.now()}`;
  }
}

openCameraWindow = async function(rackId, device){
  const win = document.getElementById("cameraWindow");
  const title = document.getElementById("cameraTitle");
  const sub = document.getElementById("cameraSub");

  if(!win) return;

  snapshotRackId = rackId;
  snapshotCameraId = null;
  snapshotCameras = [];
  title.textContent = `Кадр · Стеллаж ${rackId}`;
  sub.textContent = device || "";

  win.classList.add("show");
  win.setAttribute("aria-hidden", "false");

  try{
    await loadRackCameras(rackId);
  }catch(error){
    console.error("Не удалось получить список камер полки", error);
  }
  refreshRackCameraFrame();
};

const snapshotOriginalCloseCameraWindow = closeCameraWindow;
closeCameraWindow = function(){
  snapshotRackId = null;
  snapshotCameraId = null;
  snapshotCameras = [];
  snapshotOriginalCloseCameraWindow();
};

const cameraRefreshButton = document.getElementById("cameraRefresh");
if(cameraRefreshButton){
  cameraRefreshButton.addEventListener("click", refreshRackCameraFrame);
}

// app.js may have rendered the first state before this small override loaded.
if(typeof refresh === "function"){
  window.setTimeout(()=>refresh(), 0);
}
