(() => {
  "use strict";

  const catalog = document.querySelector("#plantCatalog");
  const languageSelect = document.querySelector("#languageSelect");
  if (!catalog) return;

  function sortPlants() {
    const items = [...catalog.children].filter((node) => node.classList?.contains("plant-chip"));
    if (items.length < 2) return;

    const locale = languageSelect?.value || document.documentElement.lang || "en";
    const collator = new Intl.Collator(locale, {
      sensitivity: "base",
      numeric: true,
      ignorePunctuation: true,
    });

    const sorted = [...items].sort((a, b) => {
      const aName = a.querySelector("strong")?.textContent?.trim() || "";
      const bName = b.querySelector("strong")?.textContent?.trim() || "";
      return collator.compare(aName, bName);
    });

    const alreadySorted = items.every((item, index) => item === sorted[index]);
    if (!alreadySorted) catalog.append(...sorted);
  }

  let scheduled = false;
  function scheduleSort() {
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      sortPlants();
    });
  }

  new MutationObserver(scheduleSort).observe(catalog, { childList: true });
  languageSelect?.addEventListener("change", scheduleSort);
  scheduleSort();
})();
