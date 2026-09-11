// Main rack page: camera access is snapshot-only. No permanent MJPEG stream is
// opened in the browser or on Raspberry Pi.

let snapshotRackId = null;

cameraButtonHtml = function(r){
  if(!r.camera_device) return "";

  return `
    <button
      class="btn btn--ghost btn--eye"
      title="Получить кадр ${escapeHtml(r.camera_device)}"
      onclick="openCameraWindow(${r.rack_id}, '${escapeHtml(r.camera_device)}')"
      aria-label="Получить кадр с камеры"
    > Кадр
      <svg class="cameraIcon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7.5 7.25 8.8 5.5h6.4l1.3 1.75h2.25c1.1 0 2 .9 2 2v8.25c0 1.1-.9 2-2 2H5.25c-1.1 0-2-.9-2-2V9.25c0-1.1.9-2 2-2H7.5Z"></path>
        <circle cx="12" cy="13" r="4"></circle>
        <circle cx="18" cy="10" r="1"></circle>
      </svg>
    </button>
  `;
};

function refreshRackCameraFrame(){
  const img = document.getElementById("cameraImg");
  if(!img || snapshotRackId == null) return;

  img.alt = "Получение кадра…";
  img.src = `/api/rack/${snapshotRackId}/camera/frame?t=${Date.now()}`;
}

openCameraWindow = function(rackId, device){
  const win = document.getElementById("cameraWindow");
  const title = document.getElementById("cameraTitle");
  const sub = document.getElementById("cameraSub");

  if(!win) return;

  snapshotRackId = rackId;
  title.textContent = `Кадр · Стеллаж ${rackId}`;
  sub.textContent = device || "";

  win.classList.add("show");
  win.setAttribute("aria-hidden", "false");
  refreshRackCameraFrame();
};

const snapshotOriginalCloseCameraWindow = closeCameraWindow;
closeCameraWindow = function(){
  snapshotRackId = null;
  snapshotOriginalCloseCameraWindow();
};

const cameraRefreshButton = document.getElementById("cameraRefresh");
if(cameraRefreshButton){
  cameraRefreshButton.addEventListener("click", refreshRackCameraFrame);
}

// app.js may have rendered the first state before this small override loaded.
// Refresh once so camera buttons immediately say "Кадр" instead of "Видео".
if(typeof refresh === "function"){
  window.setTimeout(()=>refresh(), 0);
}
