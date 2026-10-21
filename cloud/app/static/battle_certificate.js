/* Historical QR certificate: share current URL and enlarge immutable archived photos. */
(function () {
  "use strict";
  document.getElementById("print-certificate")?.addEventListener("click", () => window.print());
  const share = document.getElementById("share-certificate");
  const feedback = document.getElementById("share-feedback");
  if (share) share.addEventListener("click", async () => {
    const data = {title: document.title, url: location.href};
    if (navigator.share) {
      try { await navigator.share(data); return; } catch (e) {
        if (e.name === "AbortError") return;
      }
    }
    try {
      await navigator.clipboard.writeText(location.href);
      if (feedback) feedback.classList.remove("sr-only");
      share.classList.add("copied");
      window.setTimeout(() => {
        if (feedback) feedback.classList.add("sr-only");
        share.classList.remove("copied");
      }, 2200);
    } catch (e) {
      window.prompt("Link", location.href);
    }
  });

  const box = document.getElementById("photo-lightbox");
  if (!box) return;
  const modalImg = box.querySelector("img");
  const label = box.querySelector(".lightbox-label");
  const close = box.querySelector(".lightbox-close");
  let previousFocus = null;
  function closeModal() {
    box.hidden = true;
    document.body.style.overflow = "";
    if (previousFocus) previousFocus.focus();
  }
  for (const card of document.querySelectorAll(".photo-card")) {
    const img = card.querySelector("img");
    if (img) img.addEventListener("error", () => {
      img.dataset.unavailable = "1";
      card.setAttribute("aria-disabled", "true");
    });
    card.addEventListener("click", () => {
      if (img?.dataset.unavailable) return;
      previousFocus = document.activeElement;
      modalImg.src = card.dataset.photo;
      modalImg.alt = card.dataset.caption;
      label.textContent = card.dataset.caption;
      box.hidden = false;
      document.body.style.overflow = "hidden";
      close.focus();
    });
  }
  close.addEventListener("click", closeModal);
  box.addEventListener("click", e => { if (e.target === box) closeModal(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !box.hidden) closeModal(); });
})();