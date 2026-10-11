/* Six perspective-friendly polygons per fixed rack camera. */
(function () {
  "use strict";
  var panel = document.getElementById("rackCalibrationPanel");
  if (!panel) return;
  var dialog = document.getElementById("rackCalibrationDialog");
  var title = document.getElementById("calibrationCameraTitle");
  var cameraSelect = document.getElementById("calibrationCamera");
  var slotSelect = document.getElementById("calibrationSlot");
  var photo = document.getElementById("calibrationPhoto");
  var overlay = document.getElementById("calibrationOverlay");
  var stage = document.getElementById("calibrationStage");
  var status = document.getElementById("calibrationStatus");
  var save = document.getElementById("calibrationSave");
  var rows = [];
  var current = null;
  var outlines = {};
  var dirty = false;
  var pointer = null;
  var svgNS = "http://www.w3.org/2000/svg";
  function byId(id) { return document.getElementById(id); }
  function friendlyCamera(row) {
    var camerasOnRack = rows.filter(x =>
      x.device_id === row.device_id && Number(x.rack_id) === Number(row.rack_id));
    var index = camerasOnRack.findIndex(x => x.camera_id === row.camera_id);
    return "К" + (index + 1);
  }
  function clamp(v) { return Math.max(0, Math.min(1, v)); }
  function grid() {
    var result = {};
    for (var i = 1; i <= 6; i++) {
      var col = (i - 1) % 2;
      var row = Math.floor((i - 1) / 2);
      var left = col * .5 + .018, right = (col + 1) * .5 - .018;
      var top = row / 3 + .026, bottom = (row + 1) / 3 - .026;
      result[i] = [[left, top], [right, top], [right, bottom], [left, bottom]];
    }
    return result;
  }
  function render() {
    overlay.replaceChildren();
    for (var i = 1; i <= 6; i++) {
      var pts = outlines[i];
      if (!pts) continue;
      var selected = Number(slotSelect.value) === i;
      var poly = document.createElementNS(svgNS, "polygon");
      poly.setAttribute("points", pts.map(p => p.map(v => Math.round(v * 1000)).join(",")).join(" "));
      poly.setAttribute("class", selected ? "calibration-polygon selected" : "calibration-polygon");
      poly.dataset.slot = String(i);
      overlay.appendChild(poly);

      var x = pts.reduce((n, p) => n + p[0], 0) / 4;
      var y = pts.reduce((n, p) => n + p[1], 0) / 4;
      var badge = document.createElementNS(svgNS, "text");
      badge.setAttribute("x", String(Math.round(x * 1000)));
      badge.setAttribute("y", String(Math.round(y * 1000)));
      badge.setAttribute("class", "calibration-number");
      badge.setAttribute("pointer-events", "none");
      badge.textContent = String(i);
      overlay.appendChild(badge);
      if (selected) pts.forEach(function(p, corner) {
        var handle = document.createElementNS(svgNS, "circle");
        handle.setAttribute("cx", String(p[0] * 1000));
        handle.setAttribute("cy", String(p[1] * 1000));
        handle.setAttribute("r", "12");
        handle.setAttribute("class", "calibration-handle");
        handle.dataset.slot = String(i);
        handle.dataset.corner = String(corner);
        overlay.appendChild(handle);
      });
    }
    save.disabled = !dirty || !current;
    status.textContent = !current ? "Выберите камеру" :
      dirty ? "Есть несохранённые изменения" :
      current.slot_outlines ? "Калибровка сохранена" : "Разметка ещё не сохранялась";
  }
  function selectCamera() {
    if (dirty && !confirm("Несохранённая разметка будет потеряна. Продолжить?")) {
      cameraSelect.value = current ? rows.indexOf(current) : "";
      return;
    }
    current = rows[Number(cameraSelect.value)] || null;
    if (current) title.textContent = (current.device_name || "Теплица") +
      " · полка " + current.rack_id + " · " +
      friendlyCamera(current);
    outlines = current && current.slot_outlines ?
      JSON.parse(JSON.stringify(current.slot_outlines)) : grid();
    dirty = false;
    if (current) {
      stage.hidden = false;
      // The image determines the natural aspect ratio. Overlay is aligned to
      // the element's exact border box, not a cropped background-image.
      photo.src = current.photo_url + "?calibration=" + Date.now();
      photo.onload = function() {
        if (photo.naturalWidth && photo.naturalHeight) {
          stage.style.aspectRatio = photo.naturalWidth + " / " + photo.naturalHeight;
        }
      };
    } else {
      stage.hidden = true;
      photo.removeAttribute("src");
    }
    render();
  }
  function screenPoint(ev) {
    var rect = overlay.getBoundingClientRect();
    return [clamp((ev.clientX - rect.left) / rect.width),
      clamp((ev.clientY - rect.top) / rect.height)];
  }
  overlay.addEventListener("pointerdown", function(ev) {
    var target = ev.target;
    if (target.dataset.slot) slotSelect.value = target.dataset.slot;
    if (!target.dataset.slot) return;
    pointer = {
      id: ev.pointerId, slot: Number(target.dataset.slot),
      corner: target.dataset.corner !== undefined ? Number(target.dataset.corner) : null,
      position: screenPoint(ev),
      start: JSON.parse(JSON.stringify(outlines[target.dataset.slot]))
    };
    overlay.setPointerCapture(ev.pointerId);
    ev.preventDefault();
    render();
  });
  overlay.addEventListener("pointermove", function(ev) {
    if (!pointer || pointer.id !== ev.pointerId) return;
    var pos = screenPoint(ev);
    var dx = pos[0] - pointer.position[0];
    var dy = pos[1] - pointer.position[1];
    if (pointer.corner !== null) {
      outlines[pointer.slot][pointer.corner] = pos.map(v => Math.round(v * 10000) / 10000);
    } else {
      var x = pointer.start.map(p => p[0]);
      var y = pointer.start.map(p => p[1]);
      dx = Math.max(-Math.min(...x), Math.min(1 - Math.max(...x), dx));
      dy = Math.max(-Math.min(...y), Math.min(1 - Math.max(...y), dy));
      outlines[pointer.slot] = pointer.start.map(p => [
        Math.round((p[0] + dx) * 10000) / 10000,
        Math.round((p[1] + dy) * 10000) / 10000
      ]);
    }
    dirty = true;
    render();
  });
  ["pointerup", "pointercancel", "lostpointercapture"].forEach(function(name) {
    overlay.addEventListener(name, function() { pointer = null; });
  });
  cameraSelect.addEventListener("change", selectCamera);
  slotSelect.addEventListener("change", render);
  byId("calibrationResetSlot").addEventListener("click", function() {
    if (!current) return;
    var slot = slotSelect.value;
    outlines[slot] = grid()[slot];
    dirty = true; render();
  });
  byId("calibrationResetAll").addEventListener("click", function() {
    if (!current || !confirm("Сбросить все 6 рамок к первоначальной сетке?")) return;
    outlines = grid(); dirty = true; render();
  });
  save.addEventListener("click", async function() {
    if (!current) return;
    var old = save.textContent;
    save.disabled = true; save.textContent = "Сохранение…";
    try {
      var url = "/api/v1/admin/rack-calibrations/" +
        encodeURIComponent(current.device_id) + "/" + current.rack_id + "/" +
        encodeURIComponent(current.camera_id);
      var response = await api(url, {
        method: "PUT",
        body: JSON.stringify({slot_outlines: outlines})
      });
      current.slot_outlines = response.slot_outlines;
      dirty = false;
      toast("Все 6 рамок сохранены. Android применит их при обновлении битвы.");
    } catch(e) {
      toast("Ошибка калибровки: " + e.message);
    } finally {
      save.textContent = old;
      render();
    }
  });
  async function load(deviceId, rackId, cameraId) {
    try {
      rows = await api("/api/v1/admin/rack-calibrations");
      var selectedIndex = rows.findIndex(x =>
        x.device_id === deviceId && Number(x.rack_id) === Number(rackId) &&
        x.camera_id === cameraId);
      if (selectedIndex < 0) {
        status.textContent = "Эта камера не найдена или ещё не прислала фотографию.";
        return;
      }
      cameraSelect.replaceChildren();
      rows.forEach(function(row, i) {
        var opt = document.createElement("option");
        opt.value = String(i);
        opt.textContent = (row.device_name || "Теплица") +
          " · полка " + row.rack_id +
          " · " + friendlyCamera(row) +
          (row.slot_outlines ? " ✓" : " · не настроена");
        cameraSelect.appendChild(opt);
      });
      cameraSelect.value = String(selectedIndex);
      dirty = false;
      current = null;
      selectCamera();
    } catch(e) {
      status.textContent = "Ошибка загрузки калибровки: " + e.message;
    }
  }
  var opening = false;
  window.openRackCalibration = async function(deviceId, rackId, cameraId) {
    if (opening) return;
    opening = true;
    try {
      dirty = false;
      current = null;
      slotSelect.value = "1";
      status.textContent = "Загружаем фото и рамки…";
      dialog.showModal();
      await load(deviceId, rackId, cameraId);
    } finally { opening = false; }
  };
  function tryClose() {
    if (dirty && !confirm("Закрыть окно без сохранения рамок?")) return;
    dirty = false;
    dialog.close();
  }
  byId("calibrationClose").addEventListener("click", tryClose);
  dialog.addEventListener("cancel", function(ev) {
    if (dirty && !confirm("Закрыть окно без сохранения рамок?")) ev.preventDefault();
    else dirty = false;
  });
})();
