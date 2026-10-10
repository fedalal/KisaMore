(() => {
  "use strict";

  // Keep each currently displayed frame in the DOM while the next photo loads.
  // A downloaded AND decoded Image is swapped into place without an empty frame.
  function loadWhenReady(image) {
    const url = image.dataset.photoUrl;
    if (!url || image.dataset.loadedUrl === url || image.dataset.pendingUrl === url) return;

    image.dataset.pendingUrl = url;
    const ready = new Image();
    ready.decoding = "async";

    ready.onload = async () => {
      if (typeof ready.decode === "function") {
        try { await ready.decode(); } catch (_) {
          if (!ready.complete || !ready.naturalWidth) return;
        }
      }
      // Ignore stale requests if an update came in while this frame loaded.
      if (!image.isConnected || image.dataset.photoUrl !== url ||
          image.dataset.pendingUrl !== url || !ready.naturalWidth) return;

      ready.dataset.smoothPhoto = image.dataset.smoothPhoto;
      ready.dataset.photoUrl = url;
      ready.dataset.loadedUrl = url;
      ready.alt = image.alt;
      ready.className = image.className;
      ready.loading = image.loading || "eager";
      image.replaceWith(ready);
      const placeholder = ready.parentElement?.querySelector(".plant-image-fallback");
      if (placeholder) placeholder.classList.add("hidden");
    };
    ready.onerror = () => {
      // A failed request never replaces the last successfully displayed frame.
      if (image.dataset.pendingUrl === url) delete image.dataset.pendingUrl;
    };
    ready.src = url;
  }

  function replace(container, content) {
    if (!container) return;
    const fragment = document.createDocumentFragment();
    if (typeof content === "string") {
      const template = document.createElement("template");
      template.innerHTML = content;
      fragment.append(template.content);
    } else if (Array.isArray(content)) {
      fragment.append(...content);
    } else if (content) {
      fragment.append(content);
    }

    const oldImages = new Map();
    container.querySelectorAll("img[data-smooth-photo]").forEach(image => {
      oldImages.set(image.dataset.smoothPhoto, image);
    });
    const pictures = [];
    fragment.querySelectorAll("img[data-smooth-photo]").forEach(fresh => {
      const key = fresh.dataset.smoothPhoto;
      const existing = oldImages.get(key);
      if (existing) {
        oldImages.delete(key);
        existing.dataset.photoUrl = fresh.dataset.photoUrl;
        existing.alt = fresh.alt;
        existing.className = fresh.className;
        // Reuse the decoded image node. No new request until a changed frame
        // is loaded; previous pending requests are invalidated by photoUrl.
        fresh.replaceWith(existing);
        pictures.push(existing);
        if (existing.dataset.loadedUrl === existing.dataset.photoUrl) {
          const placeholder = existing.parentElement?.querySelector(".plant-image-fallback");
          if (placeholder) placeholder.classList.add("hidden");
        }
      } else {
        pictures.push(fresh);
      }
    });

    container.replaceChildren(fragment);
    pictures.forEach(loadWhenReady);
  }

  function versioned(url, capturedAt) {
    if (!url) return "";
    const version = encodeURIComponent(capturedAt || Date.now());
    return url + (url.includes("?") ? "&" : "?") + "v=" + version;
  }

  window.KisaMoreSmoothImages = { replace, versioned };
})();
