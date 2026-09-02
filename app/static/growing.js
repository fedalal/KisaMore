(() => {
  "use strict";

  const messages = {
    en: { dashboard: "Dashboard", operator: "Operator workspace", title: "Plants and containers", subtitle: "Manage the plant catalog and six container positions on every rack.", newPlant: "Add plant", catalog: "Plant catalog", racks: "Racks", sixSlots: "Six containers per rack", plantEditor: "Plant", code: "Code", nameEnglish: "Name (English)", nameRussian: "Name (Russian)", nameGerman: "Name (German)", nameFrench: "Name (French)", nameSpanish: "Name (Spanish)", nameItalian: "Name (Italian)", namePortuguese: "Name (Portuguese)", namePolish: "Name (Polish)", nameChinese: "Name (Chinese)", seedImageName: "Seed image filename", microgreenImageName: "Microgreen image filename", growDays: "Growing days", active: "Available for selection", cancel: "Cancel", save: "Save", startPlanting: "Start planting", plant: "Plant", plantedAt: "Planted at", notes: "Notes", start: "Start", rack: "Rack", slot: "Container", available: "Available", reserved: "Reserved", growing: "Growing", ready: "Ready", maintenance: "Cleaning", disabled: "Disabled", harvested: "Harvested", markReady: "Mark ready", finish: "Harvest", makeAvailable: "Cleaning complete", noPlants: "Add a plant to start growing.", edit: "Edit", loadError: "Could not load growing data.", saveError: "Could not save changes." },
    ru: { dashboard: "Панель", operator: "Рабочее место оператора", title: "Растения и контейнеры", subtitle: "Управление справочником растений и шестью местами на каждой полке.", newPlant: "Добавить растение", catalog: "Справочник растений", racks: "Полки", sixSlots: "Шесть контейнеров на полке", plantEditor: "Растение", code: "Код", nameEnglish: "Название (английский)", nameRussian: "Название (русский)", nameGerman: "Название (немецкий)", nameFrench: "Название (французский)", nameSpanish: "Название (испанский)", nameItalian: "Название (итальянский)", namePortuguese: "Название (португальский)", namePolish: "Название (польский)", nameChinese: "Название (китайский)", seedImageName: "Имя изображения семян", microgreenImageName: "Имя изображения микрозелени", growDays: "Дней выращивания", active: "Доступно для выбора", cancel: "Отмена", save: "Сохранить", startPlanting: "Начать выращивание", plant: "Растение", plantedAt: "Дата посадки", notes: "Комментарий", start: "Посадить", rack: "Полка", slot: "Контейнер", available: "Свободен", reserved: "Забронирован", growing: "Растёт", ready: "Готов", maintenance: "Очистка", disabled: "Отключён", harvested: "Убран", markReady: "Отметить готовым", finish: "Убрать", makeAvailable: "Очистка завершена", noPlants: "Добавьте растение, чтобы начать выращивание.", edit: "Изменить", loadError: "Не удалось загрузить данные выращивания.", saveError: "Не удалось сохранить изменения." },
    zh: { dashboard: "控制面板", operator: "操作员工作区", title: "植物和容器", subtitle: "管理植物目录和每个架子的六个容器位置。", newPlant: "添加植物", catalog: "植物目录", racks: "种植架", sixSlots: "每架六个容器", plantEditor: "植物", code: "代码", nameEnglish: "英文名称", nameRussian: "俄文名称", nameGerman: "德文名称", nameFrench: "法文名称", nameSpanish: "西班牙文名称", nameItalian: "意大利文名称", namePortuguese: "葡萄牙文名称", namePolish: "波兰文名称", nameChinese: "中文名称", seedImageName: "种子图片文件名", microgreenImageName: "微型蔬菜图片文件名", growDays: "生长天数", active: "可供选择", cancel: "取消", save: "保存", startPlanting: "开始种植", plant: "植物", plantedAt: "种植时间", notes: "备注", start: "开始", rack: "架子", slot: "容器", available: "空闲", reserved: "已预订", growing: "生长中", ready: "可收获", maintenance: "清洁中", disabled: "已停用", harvested: "已收获", markReady: "标记可收获", finish: "收获", makeAvailable: "完成清洁", noPlants: "请先添加植物。", edit: "编辑", loadError: "无法加载种植数据。", saveError: "无法保存更改。" },
  };

  const plantNameFields = [
    ["en", "nameEn"],
    ["ru", "nameRu"],
    ["de", "nameDe"],
    ["fr", "nameFr"],
    ["es", "nameEs"],
    ["it", "nameIt"],
    ["pt", "namePt"],
    ["pl", "namePl"],
    ["zh", "nameZh"],
  ];

  let language = localStorage.getItem("kisamore-language") || "en";
  if (!messages[language]) language = "en";
  let plants = [];
  let slots = [];

  const t = (key) => messages[language][key] || messages.en[key] || key;
  const plantName = (plant) => plant.names?.[language] || plant.names?.en || plant.names?.ru || plant.code;
  const $ = (selector) => document.querySelector(selector);
  const notice = $("#notice");

  function applyLanguage() {
    document.documentElement.lang = language;
    $("#languageSelect").value = language;
    document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
    render();
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", Accept: "application/json", ...(options.headers || {}) },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.status === 204 ? null : response.json();
  }

  function localDateTime() {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    return now.toISOString().slice(0, 16);
  }

  function createPlantCode(englishName) {
    const slug = String(englishName || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 60) || "plant";
    const uniquePart = window.crypto && typeof window.crypto.randomUUID === "function"
      ? window.crypto.randomUUID().replaceAll("-", "").slice(0, 8)
      : `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`.slice(-10);
    return `${slug}_${uniquePart}`;
  }

  function renderPlants() {
    const catalog = $("#plantCatalog");
    if (!plants.length) {
      catalog.textContent = t("noPlants");
      return;
    }
    catalog.replaceChildren(...plants.map((plant) => {
      const chip = document.createElement("div");
      chip.className = "plant-chip";
      const name = document.createElement("strong");
      name.textContent = plantName(plant);
      const days = document.createElement("span");
      days.textContent = `${plant.grow_days} d`;
      const edit = document.createElement("button");
      edit.type = "button";
      edit.textContent = t("edit");
      edit.addEventListener("click", () => openPlantEditor(plant));
      chip.append(name, days, edit);
      return chip;
    }));
  }

  function slotCard(slot) {
    const card = document.createElement("article");
    card.className = `slot ${slot.status}`;
    card.innerHTML = `<span class="slot-number"></span><strong></strong><small></small><div class="slot-actions"></div>`;
    card.querySelector(".slot-number").textContent = `${t("slot")} ${slot.slot_number}`;
    const planting = slot.current_planting;
    card.querySelector("strong").textContent = planting
      ? (planting.plant_names?.[language] || planting.plant_names?.en || planting.plant_code)
      : t(slot.status);
    card.querySelector("small").textContent = planting
      ? new Intl.DateTimeFormat(language, { dateStyle: "medium" }).format(new Date(planting.expected_harvest_at))
      : t(slot.status);
    const actions = card.querySelector(".slot-actions");
    if (slot.status === "available" && plants.length) {
      actions.append(actionButton(t("start"), () => openPlanting(slot)));
    } else if (planting?.status === "growing") {
      actions.append(actionButton(t("markReady"), () => updatePlanting(planting.id, { status: "ready" })));
    } else if (planting?.status === "ready") {
      actions.append(actionButton(t("finish"), () => updatePlanting(planting.id, { status: "harvested" })));
    } else if (slot.status === "maintenance") {
      actions.append(actionButton(t("makeAvailable"), () => updateSlot(slot, "available")));
    }
    return card;
  }

  function actionButton(label, handler) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", handler);
    return button;
  }

  function renderRacks() {
    const byRack = Map.groupBy ? Map.groupBy(slots, (slot) => slot.rack_id) : slots.reduce((map, slot) => map.set(slot.rack_id, [...(map.get(slot.rack_id) || []), slot]), new Map());
    const cards = [...byRack.entries()].map(([rackId, rackSlots]) => {
      const rack = document.createElement("article");
      rack.className = "rack";
      const title = document.createElement("h3");
      title.textContent = `${t("rack")} ${rackId}`;
      const grid = document.createElement("div");
      grid.className = "slots";
      grid.replaceChildren(...rackSlots.map(slotCard));
      rack.append(title, grid);
      return rack;
    });
    $("#racksGrid").replaceChildren(...cards);
  }

  function render() { renderPlants(); renderRacks(); }

  function showError(message) { notice.textContent = message; notice.classList.remove("hidden"); }
  function clearError() { notice.classList.add("hidden"); }

  async function load() {
    try {
      [plants, slots] = await Promise.all([api("/api/growing/plants?include_inactive=true"), api("/api/growing/slots")]);
      clearError();
      render();
    } catch (error) { console.error(error); showError(t("loadError")); }
  }

  function openPlantEditor(plant = null) {
    const form = $("#plantForm");
    form.reset();
    form.elements.plantId.value = plant?.id || "";
    form.elements.code.value = plant?.code || "";
    for (const [locale, field] of plantNameFields) {
      form.elements[field].value = plant?.names?.[locale] || "";
    }
    form.elements.seedImageName.value = plant?.seed_image_name || "";
    form.elements.microgreenImageName.value = plant?.microgreen_image_name || "";
    form.elements.growDays.value = plant?.grow_days || 14;
    form.elements.active.checked = plant?.active ?? true;
    $("#plantDialog").showModal();
  }

  function openPlanting(slot) {
    const form = $("#plantingForm");
    form.reset();
    form.elements.rackId.value = slot.rack_id;
    form.elements.slotNumber.value = slot.slot_number;
    form.elements.plantedAt.value = localDateTime();
    form.elements.plantId.replaceChildren(...plants.filter((plant) => plant.active).map((plant) => {
      const option = document.createElement("option");
      option.value = plant.id;
      option.textContent = plantName(plant);
      return option;
    }));
    $("#plantingDialog").showModal();
  }

  async function updatePlanting(id, payload) {
    try { await api(`/api/growing/plantings/${id}`, { method: "PATCH", body: JSON.stringify(payload) }); await load(); }
    catch (error) { console.error(error); showError(t("saveError")); }
  }

  async function updateSlot(slot, status) {
    try { await api(`/api/growing/slots/${slot.rack_id}/${slot.slot_number}`, { method: "PATCH", body: JSON.stringify({ status }) }); await load(); }
    catch (error) { console.error(error); showError(t("saveError")); }
  }

  $("#languageSelect").addEventListener("change", (event) => { language = event.target.value; localStorage.setItem("kisamore-language", language); applyLanguage(); });
  $("#newPlantButton").addEventListener("click", () => openPlantEditor());
  document.querySelectorAll("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));

  $("#plantForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const id = form.elements.plantId.value;
    const names = {};
    for (const [locale, field] of plantNameFields) {
      const value = form.elements[field].value.trim();
      if (value) names[locale] = value;
    }
    const code = form.elements.code.value.trim() || createPlantCode(names.en);
    const payload = {
      code,
      names,
      descriptions: {},
      seed_image_name: form.elements.seedImageName.value.trim(),
      microgreen_image_name: form.elements.microgreenImageName.value.trim(),
      grow_days: Number(form.elements.growDays.value),
      active: form.elements.active.checked,
    };
    try {
      await api(id ? `/api/growing/plants/${id}` : "/api/growing/plants", { method: id ? "PUT" : "POST", body: JSON.stringify(payload) });
      $("#plantDialog").close(); await load();
    } catch (error) { console.error(error); showError(t("saveError")); }
  });

  $("#plantingForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = { rack_id: Number(form.elements.rackId.value), slot_number: Number(form.elements.slotNumber.value), plant_id: form.elements.plantId.value, planted_at: new Date(form.elements.plantedAt.value).toISOString(), notes: form.elements.notes.value.trim() };
    try { await api("/api/growing/plantings", { method: "POST", body: JSON.stringify(payload) }); $("#plantingDialog").close(); await load(); }
    catch (error) { console.error(error); showError(t("saveError")); }
  });

  applyLanguage();
  load();
})();
