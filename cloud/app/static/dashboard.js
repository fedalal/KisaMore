(() => {
  "use strict";

  const refreshIntervalMs = 30_000;
  const farmSlug = document.querySelector('meta[name="kisamore-farm-slug"]').content;
  const endpoint = `/api/v1/public/farms/${encodeURIComponent(farmSlug)}/live`;

  const elements = {
    connectionPill: document.getElementById("connectionPill"),
    connectionText: document.getElementById("connectionText"),
    farmName: document.getElementById("farmName"),
    deviceName: document.getElementById("deviceName"),
    lastSeen: document.getElementById("lastSeen"),
    refreshButton: document.getElementById("refreshButton"),
    rackCount: document.getElementById("rackCount"),
    lightsOn: document.getElementById("lightsOn"),
    wateringOn: document.getElementById("wateringOn"),
    sensorsOnline: document.getElementById("sensorsOnline"),
    notice: document.getElementById("notice"),
    racksGrid: document.getElementById("racksGrid"),
    rackTemplate: document.getElementById("rackTemplate"),
    pageUpdated: document.getElementById("pageUpdated"),
  };

  let refreshTimer = null;
  let requestInProgress = false;
  let hasRenderedData = false;

  const plural = (value, one, few, many) => {
    const mod10 = value % 10;
    const mod100 = value % 100;
    if (mod10 === 1 && mod100 !== 11) return one;
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
    return many;
  };

  const parseDate = (value) => {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  };

  const relativeTime = (value) => {
    const date = value instanceof Date ? value : parseDate(value);
    if (!date) return "нет данных";

    const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
    if (seconds < 10) return "только что";
    if (seconds < 60) return `${seconds} ${plural(seconds, "секунду", "секунды", "секунд")} назад`;

    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} ${plural(minutes, "минуту", "минуты", "минут")} назад`;

    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} ${plural(hours, "час", "часа", "часов")} назад`;

    const days = Math.floor(hours / 24);
    return `${days} ${plural(days, "день", "дня", "дней")} назад`;
  };

  const exactTime = (value) => {
    const date = parseDate(value);
    if (!date) return "Время не указано";
    return new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date);
  };

  const modeLabel = (mode) => mode === "schedule" ? "по расписанию" : "вручную";

  const sensorStatus = (observedAt) => {
    const date = parseDate(observedAt);
    if (!date) return { className: "is-missing", label: "Нет данных" };

    const ageMs = Math.max(0, Date.now() - date.getTime());
    if (ageMs <= 2 * 60_000) return { className: "is-fresh", label: "Датчик активен" };
    if (ageMs <= 24 * 60 * 60_000) return { className: "is-stale", label: "Данные устарели" };
    return { className: "is-old", label: "Старые данные" };
  };

  const setConnection = (status) => {
    const labels = {
      online: "Теплица в сети",
      offline: "Теплица не в сети",
      waiting: "Ожидаем данные",
    };
    const normalized = labels[status] ? status : "waiting";
    elements.connectionPill.className = `connection-pill is-${normalized}`;
    elements.connectionText.textContent = labels[normalized];
  };

  const setEquipmentState = (card, type, isOn, mode) => {
    const container = card.querySelector(`.${type}-state`);
    const value = card.querySelector(`.${type}-value`);
    const modeValue = card.querySelector(`.${type}-mode`);
    container.classList.toggle("is-on", Boolean(isOn));
    value.textContent = isOn ? "Включён" : "Выключен";
    modeValue.textContent = modeLabel(mode);
  };

  const renderRack = (rack, rackId) => {
    const card = elements.rackTemplate.content.firstElementChild.cloneNode(true);
    const available = Boolean(rack);
    const sensor = sensorStatus(rack?.sensor_observed_at);

    card.dataset.rackId = String(rackId);
    card.classList.toggle("is-unavailable", !available);
    card.querySelector(".rack-title").textContent = `Полка ${rackId}`;

    const badge = card.querySelector(".sensor-badge");
    badge.classList.add(sensor.className);
    badge.querySelector(".sensor-badge-text").textContent = available ? sensor.label : "Нет состояния";

    setEquipmentState(card, "light", rack?.light_on, rack?.light_mode);
    setEquipmentState(card, "water", rack?.water_on, rack?.water_mode);

    const temperature = rack?.soil_temperature;
    const moisture = rack?.soil_moisture;
    card.querySelector(".temperature-value").textContent =
      Number.isFinite(temperature) ? `${temperature.toFixed(1)} °C` : "—";
    card.querySelector(".moisture-value").textContent =
      Number.isFinite(moisture) ? `${moisture.toFixed(1)} %` : "—";

    const camera = card.querySelector(".camera-state");
    const hasCamera = Boolean(rack?.camera_id);
    camera.classList.toggle("has-camera", hasCamera);
    card.querySelector(".camera-value").textContent = hasCamera ? "Камера подключена" : "Нет камеры";
    card.querySelector(".camera-id").textContent = hasCamera ? rack.camera_id : "";

    const rackUpdated = card.querySelector(".rack-updated");
    rackUpdated.textContent = rack?.observed_at ? relativeTime(rack.observed_at) : "нет данных";
    if (rack?.observed_at) rackUpdated.dateTime = rack.observed_at;
    rackUpdated.title = rack?.observed_at ? exactTime(rack.observed_at) : "Время не указано";

    return card;
  };

  const render = (data) => {
    const racks = Array.isArray(data.racks) ? data.racks : [];
    const racksById = new Map(racks.map((rack) => [rack.rack_id, rack]));
    const rackCount = Math.max(0, Number(data.racks_count) || racks.length);

    setConnection(data.status);
    elements.farmName.textContent = data.farm_name || "KisaMore Farm";
    elements.deviceName.textContent = data.device_name || data.device_id || "Устройство";
    elements.lastSeen.textContent = data.last_seen_at
      ? `Последняя связь ${relativeTime(data.last_seen_at)}`
      : "Ожидаем первые данные";
    elements.lastSeen.title = data.last_seen_at ? exactTime(data.last_seen_at) : "";

    elements.rackCount.textContent = String(rackCount);
    elements.lightsOn.textContent = String(racks.filter((rack) => rack.light_on).length);
    elements.wateringOn.textContent = String(racks.filter((rack) => rack.water_on).length);
    elements.sensorsOnline.textContent = String(
      racks.filter((rack) => rack.sensor_observed_at !== null).length,
    );

    const fragment = document.createDocumentFragment();
    for (let rackId = 1; rackId <= rackCount; rackId += 1) {
      fragment.appendChild(renderRack(racksById.get(rackId), rackId));
    }
    elements.racksGrid.replaceChildren(fragment);
    elements.racksGrid.setAttribute("aria-busy", "false");

    document.title = `${data.farm_name || "KisaMore Farm"} — состояние теплицы`;
    elements.pageUpdated.textContent = `Обновлено ${new Intl.DateTimeFormat("ru-RU", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date())}`;
    hasRenderedData = true;
  };

  const setLoading = (loading) => {
    requestInProgress = loading;
    elements.refreshButton.disabled = loading;
    elements.refreshButton.classList.toggle("is-loading", loading);
    elements.racksGrid.setAttribute("aria-busy", String(loading));
  };

  const showError = () => {
    elements.notice.textContent = hasRenderedData
      ? "Не удалось получить свежие данные. На экране оставлено последнее успешно загруженное состояние."
      : "Не удалось загрузить состояние теплицы. Проверьте соединение и попробуйте ещё раз.";
    elements.notice.classList.remove("is-hidden");
    if (!hasRenderedData) {
      setConnection("offline");
      elements.racksGrid.innerHTML = '<div class="loading-card">Данные временно недоступны</div>';
    }
  };

  const scheduleRefresh = () => {
    window.clearTimeout(refreshTimer);
    refreshTimer = window.setTimeout(loadData, refreshIntervalMs);
  };

  const loadData = async () => {
    if (requestInProgress) return;
    setLoading(true);

    try {
      const response = await fetch(endpoint, {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      render(data);
      elements.notice.classList.add("is-hidden");
    } catch (error) {
      console.error("KisaMore dashboard refresh failed", error);
      showError();
    } finally {
      setLoading(false);
      scheduleRefresh();
    }
  };

  elements.refreshButton.addEventListener("click", loadData);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) loadData();
  });

  loadData();
})();
