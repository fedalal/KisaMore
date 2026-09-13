(() => {
  "use strict";

  const dialog = document.querySelector("#plantDialog");
  const form = document.querySelector("#plantForm");
  const languageSelect = document.querySelector("#languageSelect");
  const host = document.querySelector("#factsEditorHost");
  const tabButton = document.querySelector('[data-plant-tab="facts"]');
  if (!dialog || !form || !host || !tabButton) return;

  const previousFetch = window.fetch.bind(window);
  const locales = [
    ["en", "English"], ["ru", "Русский"], ["de", "Deutsch"],
    ["fr", "Français"], ["es", "Español"], ["it", "Italiano"],
    ["pt", "Português"], ["pl", "Polski"], ["zh", "中文"],
  ];
  const copy = {
    en: {
      tab: "Interesting facts",
      title: "Interesting facts for watering messages",
      help: "One fact per line. The bot rotates these facts without repeating them until the list is exhausted. Up to 40 facts per language.",
      count: "facts",
    },
    ru: {
      tab: "Интересные факты",
      title: "Интересные факты для сообщений о поливе",
      help: "Один факт на строку. Бот будет использовать их по очереди без повторов, пока список не закончится. До 40 фактов на язык.",
      count: "фактов",
    },
    zh: {
      tab: "趣味知识",
      title: "用于浇水通知的植物趣味知识",
      help: "每行一个事实。机器人会依次使用，直到列表用完再循环。每种语言最多 40 条。",
      count: "条",
    },
  };

  host.innerHTML = `
    <div class="facts-editor-head">
      <h3 id="factsTitle"></h3>
      <p id="factsHelp"></p>
    </div>
    <div id="factsGrid" class="plant-name-grid"></div>`;
  const grid = host.querySelector("#factsGrid");

  for (const [locale, label] of locales) {
    const field = document.createElement("label");
    field.className = "facts-field";
    field.innerHTML = `
      <span>${label} <small class="facts-count" data-facts-count="${locale}"></small></span>
      <textarea name="facts_${locale}" rows="10" maxlength="24000" spellcheck="true"></textarea>`;
    grid.append(field);
  }

  function lang() {
    const value = languageSelect?.value || "en";
    return copy[value] ? value : "en";
  }

  function tr(key) {
    return copy[lang()][key] || copy.en[key] || key;
  }

  function factLines(locale) {
    const value = String(form.elements[`facts_${locale}`]?.value || "");
    return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean).slice(0, 40);
  }

  function updateCount(locale) {
    const node = host.querySelector(`[data-facts-count="${locale}"]`);
    if (node) node.textContent = `· ${factLines(locale).length}/40 ${tr("count")}`;
  }

  function updateCounts() {
    for (const [locale] of locales) updateCount(locale);
  }

  function applyLanguage() {
    tabButton.textContent = tr("tab");
    host.querySelector("#factsTitle").textContent = tr("title");
    host.querySelector("#factsHelp").textContent = tr("help");
    updateCounts();
  }

  function renderFacts(plant) {
    for (const [locale] of locales) {
      form.elements[`facts_${locale}`].value = (plant?.facts?.[locale] || []).join("\n");
    }
    updateCounts();
  }

  function readFacts() {
    const facts = {};
    for (const [locale] of locales) {
      const values = factLines(locale);
      if (values.length) facts[locale] = values;
    }
    return facts;
  }

  async function allPlants() {
    const response = await previousFetch("/api/growing/plants?include_inactive=true", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return [];
    return response.json();
  }

  async function fillForOpenDialog() {
    if (!dialog.open) return;
    const id = form.elements.plantId.value;
    if (!id) {
      renderFacts(null);
      return;
    }
    try {
      const plants = await allPlants();
      renderFacts(plants.find((item) => item.id === id) || null);
    } catch (_) {
      renderFacts(null);
    }
  }

  for (const [locale] of locales) {
    form.elements[`facts_${locale}`].addEventListener("input", () => updateCount(locale));
  }
  languageSelect?.addEventListener("change", applyLanguage);
  const observer = new MutationObserver(() => { if (dialog.open) fillForOpenDialog(); });
  observer.observe(dialog, { attributes: true, attributeFilter: ["open"] });
  applyLanguage();

  window.fetch = async function factsFetch(input, init = {}) {
    const url = typeof input === "string" ? input : input?.url || "";
    const method = String(init.method || "GET").toUpperCase();
    const isPlantWrite = (method === "POST" || method === "PUT") &&
      (url === "/api/growing/plants" || url.startsWith("/api/growing/plants/"));

    if (!isPlantWrite || typeof init.body !== "string") return previousFetch(input, init);

    let payload;
    try { payload = JSON.parse(init.body); }
    catch (_) { return previousFetch(input, init); }

    if (dialog.open) {
      payload.facts = readFacts();
    } else if (method === "PUT") {
      const plantId = decodeURIComponent(url.split("/").pop() || "");
      try {
        const plants = await allPlants();
        const current = plants.find((item) => item.id === plantId);
        if (current) payload.facts ??= current.facts || {};
      } catch (_) {}
    }
    return previousFetch(input, { ...init, body: JSON.stringify(payload) });
  };
})();
