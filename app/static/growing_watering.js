(() => {
  "use strict";

  const dialog = document.querySelector("#plantDialog");
  const form = document.querySelector("#plantForm");
  const languageSelect = document.querySelector("#languageSelect");
  if (!dialog || !form) return;

  const previousFetch = window.fetch.bind(window);
  const text = {
    en: {
      title: "Individual watering",
      help: "Watering is performed manually per container. These settings create reminders for the administrator on the VPS.",
      schedule: "Daily schedule",
      addTime: "+ Add watering",
      time: "Time",
      ml: "ml",
      remove: "Remove",
      rules: "User adjustment",
      limit: "Maximum change (%)",
      step: "Adjustment step (%)",
      interval: "Minimum interval (minutes)",
      extras: "Extra watering options",
      addExtra: "+ Add option",
      price: "Price (Ⓚ)",
      noSchedule: "No scheduled watering yet.",
    },
    ru: {
      title: "Индивидуальный полив",
      help: "Полив выполняется вручную для каждого контейнера. Эти настройки создают задания и напоминания администратору на VPS.",
      schedule: "Расписание на каждый день",
      addTime: "+ Добавить полив",
      time: "Время",
      ml: "мл",
      remove: "Удалить",
      rules: "Настройка пользователем",
      limit: "Максимальное изменение (%)",
      step: "Шаг изменения (%)",
      interval: "Минимальный интервал (минут)",
      extras: "Дополнительный полив",
      addExtra: "+ Добавить вариант",
      price: "Цена (Ⓚ)",
      noSchedule: "Плановый полив пока не задан.",
    },
    zh: {
      title: "单独浇水",
      help: "每个容器手动浇水。这些设置会在 VPS 上为管理员创建浇水任务。",
      schedule: "每日计划",
      addTime: "+ 添加浇水",
      time: "时间",
      ml: "毫升",
      remove: "删除",
      rules: "用户调整",
      limit: "最大调整 (%)",
      step: "调整步长 (%)",
      interval: "最小间隔（分钟）",
      extras: "额外浇水选项",
      addExtra: "+ 添加选项",
      price: "价格 (Ⓚ)",
      noSchedule: "尚未设置计划浇水。",
    },
  };

  const editor = document.createElement("section");
  editor.id = "wateringEditor";
  editor.className = "watering-editor";
  editor.innerHTML = `
    <div class="watering-title-row">
      <div><h3 id="wateringTitle"></h3><p id="wateringHelp"></p></div>
    </div>
    <div class="watering-block">
      <div class="watering-block-head"><strong id="wateringScheduleTitle"></strong><button type="button" id="addWateringTime" class="secondary"></button></div>
      <div id="wateringScheduleRows" class="watering-rows"></div>
      <div id="wateringScheduleEmpty" class="watering-empty"></div>
    </div>
    <div class="watering-block">
      <strong id="wateringRulesTitle"></strong>
      <div class="watering-rule-grid">
        <label><span id="wateringLimitLabel"></span><input name="wateringAdjustmentLimit" type="number" min="0" max="50" value="20" required></label>
        <label><span id="wateringStepLabel"></span><input name="wateringAdjustmentStep" type="number" min="1" max="25" value="10" required></label>
        <label><span id="wateringIntervalLabel"></span><input name="wateringMinInterval" type="number" min="30" max="1440" value="240" required></label>
      </div>
    </div>
    <div class="watering-block">
      <div class="watering-block-head"><strong id="extraWateringTitle"></strong><button type="button" id="addExtraWatering" class="secondary"></button></div>
      <div id="extraWateringRows" class="watering-rows"></div>
    </div>`;

  const activeLabel = form.querySelector("label.checkbox");
  if (activeLabel) form.insertBefore(editor, activeLabel);
  else form.append(editor);

  const scheduleRows = editor.querySelector("#wateringScheduleRows");
  const scheduleEmpty = editor.querySelector("#wateringScheduleEmpty");
  const extraRows = editor.querySelector("#extraWateringRows");

  function lang() {
    const value = languageSelect?.value || "en";
    return text[value] ? value : "en";
  }

  function tr(key) {
    return text[lang()][key] || text.en[key] || key;
  }

  function applyLanguage() {
    editor.querySelector("#wateringTitle").textContent = tr("title");
    editor.querySelector("#wateringHelp").textContent = tr("help");
    editor.querySelector("#wateringScheduleTitle").textContent = tr("schedule");
    editor.querySelector("#addWateringTime").textContent = tr("addTime");
    editor.querySelector("#wateringRulesTitle").textContent = tr("rules");
    editor.querySelector("#wateringLimitLabel").textContent = tr("limit");
    editor.querySelector("#wateringStepLabel").textContent = tr("step");
    editor.querySelector("#wateringIntervalLabel").textContent = tr("interval");
    editor.querySelector("#extraWateringTitle").textContent = tr("extras");
    editor.querySelector("#addExtraWatering").textContent = tr("addExtra");
    scheduleEmpty.textContent = tr("noSchedule");
    editor.querySelectorAll(".watering-remove").forEach((button) => { button.textContent = tr("remove"); });
    editor.querySelectorAll(".watering-ml-label").forEach((node) => { node.textContent = tr("ml"); });
    editor.querySelectorAll(".watering-time-label").forEach((node) => { node.textContent = tr("time"); });
    editor.querySelectorAll(".watering-price-label").forEach((node) => { node.textContent = tr("price"); });
  }

  function updateEmpty() {
    scheduleEmpty.hidden = scheduleRows.children.length > 0;
  }

  function addScheduleRow(value = { time: "09:00", ml: 60 }) {
    const row = document.createElement("div");
    row.className = "watering-row";
    row.innerHTML = `
      <label><span class="watering-time-label"></span><input class="watering-time" type="time" required></label>
      <label><span class="watering-ml-label"></span><input class="watering-ml" type="number" min="1" max="2000" required></label>
      <button type="button" class="watering-remove danger"></button>`;
    row.querySelector(".watering-time").value = value.time || "09:00";
    row.querySelector(".watering-ml").value = String(value.ml || 60);
    row.querySelector(".watering-remove").addEventListener("click", () => { row.remove(); updateEmpty(); });
    scheduleRows.append(row);
    updateEmpty();
    applyLanguage();
  }

  function addExtraRow(value = { ml: 30, price_kisa: 1 }) {
    const row = document.createElement("div");
    row.className = "watering-row extra-row";
    row.innerHTML = `
      <label><span class="watering-ml-label"></span><input class="extra-ml" type="number" min="1" max="2000" required></label>
      <label><span class="watering-price-label"></span><input class="extra-price" type="number" min="0" max="1000000" required></label>
      <button type="button" class="watering-remove danger"></button>`;
    row.querySelector(".extra-ml").value = String(value.ml || 30);
    row.querySelector(".extra-price").value = String(value.price_kisa ?? 1);
    row.querySelector(".watering-remove").addEventListener("click", () => row.remove());
    extraRows.append(row);
    applyLanguage();
  }

  function renderConfig(plant) {
    scheduleRows.replaceChildren();
    extraRows.replaceChildren();

    if (plant) {
      for (const item of plant.watering_schedule || []) addScheduleRow(item);
      for (const item of plant.extra_watering_options || []) addExtraRow(item);
      form.elements.wateringAdjustmentLimit.value = String(plant.watering_adjustment_limit_percent ?? 20);
      form.elements.wateringAdjustmentStep.value = String(plant.watering_adjustment_step_percent ?? 10);
      form.elements.wateringMinInterval.value = String(plant.watering_min_interval_minutes ?? 240);
    } else {
      addScheduleRow({ time: "09:00", ml: 60 });
      addScheduleRow({ time: "19:00", ml: 60 });
      addExtraRow({ ml: 30, price_kisa: 1 });
      addExtraRow({ ml: 60, price_kisa: 1 });
      addExtraRow({ ml: 100, price_kisa: 2 });
      form.elements.wateringAdjustmentLimit.value = "20";
      form.elements.wateringAdjustmentStep.value = "10";
      form.elements.wateringMinInterval.value = "240";
    }
    updateEmpty();
    applyLanguage();
  }

  function readConfig() {
    const schedule = [...scheduleRows.querySelectorAll(".watering-row")].map((row) => ({
      time: row.querySelector(".watering-time").value,
      ml: Number(row.querySelector(".watering-ml").value),
    })).sort((a, b) => a.time.localeCompare(b.time));
    const times = schedule.map((item) => item.time);
    if (new Set(times).size !== times.length) throw new Error("Duplicate watering time");

    const extra = [...extraRows.querySelectorAll(".watering-row")].map((row) => ({
      ml: Number(row.querySelector(".extra-ml").value),
      price_kisa: Number(row.querySelector(".extra-price").value),
    })).sort((a, b) => a.ml - b.ml);
    const volumes = extra.map((item) => item.ml);
    if (new Set(volumes).size !== volumes.length) throw new Error("Duplicate extra watering volume");

    return {
      watering_schedule: schedule,
      watering_adjustment_limit_percent: Number(form.elements.wateringAdjustmentLimit.value),
      watering_adjustment_step_percent: Number(form.elements.wateringAdjustmentStep.value),
      watering_min_interval_minutes: Number(form.elements.wateringMinInterval.value),
      extra_watering_options: extra,
    };
  }

  async function allPlants() {
    const response = await previousFetch("/api/growing/plants?include_inactive=true", { headers: { Accept: "application/json" } });
    if (!response.ok) return [];
    return response.json();
  }

  async function fillForOpenDialog() {
    if (!dialog.open) return;
    const id = form.elements.plantId.value;
    if (!id) {
      renderConfig(null);
      return;
    }
    try {
      const plants = await allPlants();
      renderConfig(plants.find((item) => item.id === id) || null);
    } catch (_) {
      renderConfig(null);
    }
  }

  editor.querySelector("#addWateringTime").addEventListener("click", () => addScheduleRow({ time: "12:00", ml: 60 }));
  editor.querySelector("#addExtraWatering").addEventListener("click", () => addExtraRow({ ml: 30, price_kisa: 1 }));
  languageSelect?.addEventListener("change", applyLanguage);

  const observer = new MutationObserver(() => { if (dialog.open) fillForOpenDialog(); });
  observer.observe(dialog, { attributes: true, attributeFilter: ["open"] });
  applyLanguage();

  window.fetch = async function wateringFetch(input, init = {}) {
    const url = typeof input === "string" ? input : input?.url || "";
    const method = String(init.method || "GET").toUpperCase();
    const isPlantWrite = (method === "POST" || method === "PUT") &&
      (url === "/api/growing/plants" || url.startsWith("/api/growing/plants/"));

    if (!isPlantWrite || typeof init.body !== "string") return previousFetch(input, init);

    let payload;
    try { payload = JSON.parse(init.body); }
    catch (_) { return previousFetch(input, init); }

    if (dialog.open) {
      Object.assign(payload, readConfig());
    } else if (method === "PUT") {
      const plantId = decodeURIComponent(url.split("/").pop() || "");
      try {
        const plants = await allPlants();
        const current = plants.find((item) => item.id === plantId);
        if (current) {
          payload.rental_price_kisa ??= current.rental_price_kisa ?? 20;
          payload.watering_schedule ??= current.watering_schedule || [];
          payload.watering_adjustment_limit_percent ??= current.watering_adjustment_limit_percent ?? 20;
          payload.watering_adjustment_step_percent ??= current.watering_adjustment_step_percent ?? 10;
          payload.watering_min_interval_minutes ??= current.watering_min_interval_minutes ?? 240;
          payload.extra_watering_options ??= current.extra_watering_options || [];
        }
      } catch (_) {}
    }
    return previousFetch(input, { ...init, body: JSON.stringify(payload) });
  };
})();
