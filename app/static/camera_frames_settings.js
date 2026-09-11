// Snapshot-only camera UI. The original cameras.js keeps all configuration,
// warp-point and save logic; this layer replaces permanent MJPEG previews with
// explicit one-shot frames and exposes the photo controls validated on hardware.

function changeCaptureNumber(field, value){
  if(!cfgState) return;
  cfgState.camera_capture = cfgState.camera_capture || {
    frame_width: 2592,
    frame_height: 1944,
    jpeg_quality: 90
  };

  const n = Number(value);
  if(!Number.isFinite(n)) return;
  cfgState.camera_capture[field] = n;
}

function renderCaptureSettings(){
  const wrap = document.getElementById("cameraCaptureSettings");
  if(!wrap || !cfgState) return;

  const capture = cfgState.camera_capture || {};
  if(capture.frame_width == null) capture.frame_width = 2592;
  if(capture.frame_height == null) capture.frame_height = 1944;
  if(capture.jpeg_quality == null) capture.jpeg_quality = 90;
  cfgState.camera_capture = capture;

  wrap.innerHTML = `
    <section class="cameraSettingsCard">
      <div class="cameraSettingsHead">
        <div>
          <div class="cameraSettingsTitle">Параметры снимка</div>
          <div class="cameraSettingsSub">Прямой эфир отключён · камера открывается только на время одного кадра</div>
        </div>
      </div>
      <div class="cameraSettingsGrid">
        <label>
          <span>Ширина</span>
          <input class="cfgInput" type="number" min="320" max="3840" step="1"
                 value="${Number(capture.frame_width)}"
                 onchange="changeCaptureNumber('frame_width', this.value)">
        </label>
        <label>
          <span>Высота</span>
          <input class="cfgInput" type="number" min="240" max="2160" step="1"
                 value="${Number(capture.frame_height)}"
                 onchange="changeCaptureNumber('frame_height', this.value)">
        </label>
        <label>
          <span>JPEG quality</span>
          <input class="cfgInput" type="number" min="30" max="100" step="1"
                 value="${Number(capture.jpeg_quality)}"
                 onchange="changeCaptureNumber('jpeg_quality', this.value)">
        </label>
        <label>
          <span>Формат камеры</span>
          <input class="cfgInput" value="MJPG" disabled>
        </label>
      </div>
      <div class="hint">Для наших камер используем 2592×1944 MJPG. Режим 3840×2160 оказался нестабильным и давал серые участки кадра.</div>
    </section>
  `;
}

const cameraFramesOriginalCard = cameraCard;
cameraCard = function(cameraId){
  const cam = cfgState.cameras[cameraId];

  if(cam.autofocus_enabled === undefined) cam.autofocus_enabled = false;
  if(cam.focus_absolute === undefined || cam.focus_absolute === null) cam.focus_absolute = 120;
  if(cam.brightness === undefined || cam.brightness === null) cam.brightness = 1;
  if(cam.contrast === undefined || cam.contrast === null) cam.contrast = 8;
  if(cam.saturation === undefined || cam.saturation === null) cam.saturation = 10;
  if(cam.sharpness === undefined || cam.sharpness === null) cam.sharpness = 0;
  if(cam.white_balance_auto === undefined) cam.white_balance_auto = false;
  if(cam.white_balance_temperature === undefined || cam.white_balance_temperature === null) cam.white_balance_temperature = 5;

  let html = cameraFramesOriginalCard(cameraId);

  // Old markup is reused, but every image URL now performs exactly one capture.
  html = html.replaceAll("/stream?", "/frame?");
  html = html.replace("Скрыть изображения", "Обновить кадр");
  html = html.replace("Показать изображения", "Получить кадр");
  html = html.replace(
    "Изображения отключены. Нажми «Показать изображения» для просмотра и настройки.",
    "Кадр ещё не получен. Нажми «Получить кадр» для просмотра и настройки."
  );
  html = html.replace("<span>Баланс белого</span>", "<span>Баланс белого 1–5</span>");
  html = html.replace('max="10000"', 'max="5"');

  const extraControls = `
        <label>
          <span>Яркость 0–10</span>
          <input class="cfgInput" type="number" min="0" max="10" step="1"
                 value="${cam.brightness ?? 1}"
                 onchange="changeCameraNumber('${escapeHtml(cameraId)}', 'brightness', this.value)">
        </label>

        <label>
          <span>Контраст 0–20</span>
          <input class="cfgInput" type="number" min="0" max="20" step="1"
                 value="${cam.contrast ?? 8}"
                 onchange="changeCameraNumber('${escapeHtml(cameraId)}', 'contrast', this.value)">
        </label>

        <label>
          <span>Насыщенность 0–20</span>
          <input class="cfgInput" type="number" min="0" max="20" step="1"
                 value="${cam.saturation ?? 10}"
                 onchange="changeCameraNumber('${escapeHtml(cameraId)}', 'saturation', this.value)">
        </label>

        <label>
          <span>Резкость 0–20</span>
          <input class="cfgInput" type="number" min="0" max="20" step="1"
                 value="${cam.sharpness ?? 0}"
                 onchange="changeCameraNumber('${escapeHtml(cameraId)}', 'sharpness', this.value)">
        </label>
  `;

  html = html.replace(
    '<label class="cameraWarpText">',
    `${extraControls}\n        <label class="cameraWarpText">`
  );

  return html;
};

const cameraFramesOriginalRender = renderCameras;
renderCameras = function(){
  renderCaptureSettings();
  cameraFramesOriginalRender();
};

// Clicking the button the first time reveals and captures the pair of snapshots.
// Further clicks refresh them; it never opens a permanent stream.
toggleCameraPreviews = function(cameraId){
  if(picking.cameraId && picking.cameraId !== cameraId){
    picking = { cameraId: null, points: [] };
  }

  if(visibleCameraId !== cameraId){
    visibleCameraId = cameraId;
    renderCameras();
    return;
  }

  refreshVisibleCameraPreviews();
};

refreshCameraPreview = function(cameraId, corrected){
  const suffix = corrected ? "corrected" : "raw";
  const img = document.getElementById(`cameraImg_${suffix}_${cameraId}`);
  if(!img) return;

  img.src = `/api/camera/${encodeURIComponent(cameraId)}/frame?corrected=${corrected ? "true" : "false"}&t=${Date.now()}`;
};

refreshVisibleCameraPreviews = async function(){
  if(!visibleCameraId) return;

  // Both requests are one-shot captures. The per-device backend lock serializes
  // them, so even raw/corrected previews can never create parallel streams.
  refreshCameraPreview(visibleCameraId, false);
  await wait(100);
  refreshCameraPreview(visibleCameraId, true);
};
