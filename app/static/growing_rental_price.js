(() => {
  "use strict";

  const labels = {
    en: "Rental price (Kisa)",
    ru: "Цена аренды (Kisa)",
    zh: "租赁价格 (Kisa)",
  };

  const dialog = document.querySelector("#plantDialog");
  const form = document.querySelector("#plantForm");
  const languageSelect = document.querySelector("#languageSelect");
  const label = document.querySelector("#rentalPriceLabel");
  if (!dialog || !form || !label) return;

  const priceInput = form.elements.rentalPriceKisa;
  const originalFetch = window.fetch.bind(window);

  function applyLabel() {
    const lang = languageSelect?.value || "en";
    label.textContent = labels[lang] || labels.en;
  }

  async function fillPrice() {
    if (!dialog.open) return;
    const id = form.elements.plantId.value;
    if (!id) {
      priceInput.value = "20";
      return;
    }
    try {
      const response = await originalFetch("/api/growing/plants?include_inactive=true", {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) return;
      const plants = await response.json();
      const plant = plants.find((item) => item.id === id);
      priceInput.value = String(plant?.rental_price_kisa ?? 20);
    } catch (_) {
      // The main growing UI will show its own load errors when needed.
    }
  }

  const observer = new MutationObserver(() => {
    if (dialog.open) fillPrice();
  });
  observer.observe(dialog, { attributes: true, attributeFilter: ["open"] });

  languageSelect?.addEventListener("change", applyLabel);
  applyLabel();

  window.fetch = async function patchedFetch(input, init = {}) {
    const url = typeof input === "string" ? input : input?.url || "";
    const method = String(init.method || "GET").toUpperCase();
    const isPlantWrite =
      dialog.open &&
      (method === "POST" || method === "PUT") &&
      (url === "/api/growing/plants" || url.startsWith("/api/growing/plants/"));

    if (isPlantWrite && typeof init.body === "string") {
      try {
        const payload = JSON.parse(init.body);
        const price = Number(priceInput.value);
        payload.rental_price_kisa = Number.isFinite(price) ? Math.max(0, Math.trunc(price)) : 20;
        init = { ...init, body: JSON.stringify(payload) };
      } catch (_) {}
    }
    return originalFetch(input, init);
  };
})();
