(() => {
  "use strict";

  const grid = document.querySelector("#rackPhotosGrid");
  if (!grid) return;

  let loading = false;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  async function loadRows() {
    const response = await fetch("/api/v1/admin/rack-photos", {
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async function enhanceCards() {
    if (loading) return;
    const cards = [...grid.querySelectorAll(".camera-card")];
    if (!cards.length || cards.every((card) => card.querySelector(".camera-slots-wrap"))) return;

    loading = true;
    try {
      const rows = await loadRows();
      cards.forEach((card, index) => {
        if (card.querySelector(".camera-slots-wrap")) return;
        const item = rows[index];
        if (!item || !item.has_photo) return;

        const urls = item.slot_photo_urls || {};
        const available = Object.keys(urls).length;
        const slots = Array.from({ length: 6 }, (_, offset) => {
          const slot = offset + 1;
          const url = urls[String(slot)];
          const body = url
            ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener"><img src="${escapeHtml(url)}?t=${encodeURIComponent(item.updated_at || Date.now())}" alt="Контейнер ${slot}"></a>`
            : `<div class="camera-slot-empty">Ожидаем новый кадр</div>`;
          return `<figure class="camera-slot-card"><figcaption>Контейнер ${slot}</figcaption>${body}</figure>`;
        }).join("");

        const wrap = document.createElement("div");
        wrap.className = "camera-slots-wrap";
        wrap.innerHTML = `
          <button type="button" class="camera-slots-toggle">
            Показать контейнеры${available ? ` (${available}/6)` : ""}
          </button>
          <div class="camera-slot-grid" hidden>${slots}</div>
        `;

        const meta = card.querySelector(".camera-meta");
        card.insertBefore(wrap, meta || null);

        const button = wrap.querySelector(".camera-slots-toggle");
        const slotGrid = wrap.querySelector(".camera-slot-grid");
        button.addEventListener("click", () => {
          slotGrid.hidden = !slotGrid.hidden;
          button.textContent = slotGrid.hidden
            ? `Показать контейнеры${available ? ` (${available}/6)` : ""}`
            : "Скрыть контейнеры";
        });
      });
    } catch (error) {
      console.error("Could not load container crops", error);
    } finally {
      loading = false;
    }
  }

  const observer = new MutationObserver(() => enhanceCards());
  observer.observe(grid, { childList: true });
  enhanceCards();
})();
