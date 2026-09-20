(() => {
  "use strict";

  if (typeof api !== "function" || typeof esc !== "function" || typeof fmtDate !== "function") return;

  const LANGUAGE_NAMES = {
    all: "Все языки", ru: "Русский", en: "English", de: "Deutsch", fr: "Français",
    es: "Español", it: "Italiano", pt: "Português", pl: "Polski", zh: "中文",
  };
  const STATUS_NAMES = {
    pending: "В очереди", sending: "Отправляется", completed: "Завершена", cancelled: "Отменена",
  };
  const MODE_NAMES = {
    none: "Обычное сообщение", single: "Опрос · один ответ", multiple: "Опрос · несколько ответов",
  };

  let currentBroadcastId = null;
  let refreshInFlight = false;

  function statusBadge(status) {
    const cls = status === "completed" ? "green" : status === "cancelled" ? "red" : "";
    return `<span class="badge ${cls}">${esc(STATUS_NAMES[status] || status)}</span>`;
  }

  async function refreshBroadcastDetail(id, { quiet = false } = {}) {
    if (!id || refreshInFlight) return;
    const detail = document.querySelector("#broadcastDetail");
    if (!detail) return;
    refreshInFlight = true;
    try {
      const item = await api(`/api/v1/admin/telegram-broadcasts/${id}`);
      if (currentBroadcastId !== id) return;

      let media = "";
      if (item.media_url) {
        const src = `${esc(item.media_url)}?t=${encodeURIComponent(item.created_at || Date.now())}`;
        if (item.media_kind === "video") {
          media = `<video class="broadcast-detail-photo" src="${src}" controls preload="metadata" playsinline></video>`;
        } else {
          media = `<img class="broadcast-detail-photo" src="${src}" alt="Медиа рассылки">`;
        }
      }
      const text = item.text ? `<div class="broadcast-message">${esc(item.text)}</div>` : "";
      const question = item.question ? `<h3 style="margin-top:14px">${esc(item.question)}</h3>` : "";
      const results = item.options?.length
        ? `<div class="broadcast-results">${item.options.map((option) =>
            `<div class="broadcast-result"><strong>${esc(option.text)}</strong><span>${Number(option.vote_count || 0).toLocaleString("ru-RU")}</span><span>${Number(option.percentage_of_respondents || 0).toFixed(1)}%</span></div>`
          ).join("")}</div>`
        : "";

      detail.hidden = false;
      detail.innerHTML = `
        <div class="panel-head"><div><h2>Рассылка #${esc(item.id)}</h2><p>${esc(LANGUAGE_NAMES[item.language_code] || item.language_code)} · ${esc(MODE_NAMES[item.answer_mode] || item.answer_mode)} · ${esc(fmtDate(item.created_at))}</p></div>${statusBadge(item.status)}</div>
        <div class="watering-note">Получателей: ${esc(item.total_recipients)} · отправлено: ${esc(item.sent_count)} · ошибок: ${esc(item.failed_count)}${item.answer_mode !== "none" ? ` · ответили: ${esc(item.answered_users)} (${Number(item.response_rate || 0).toFixed(1)}%)` : ""}</div>
        ${media}${text}${question}${results}
        <div class="broadcast-small" style="margin-top:10px">Результаты обновляются автоматически.</div>`;
    } catch (error) {
      if (!quiet && currentBroadcastId === id) {
        const detail = document.querySelector("#broadcastDetail");
        if (detail) detail.innerHTML = `<div class="muted">Ошибка обновления результатов: ${esc(error.message)}</div>`;
      }
    } finally {
      refreshInFlight = false;
    }
  }

  document.addEventListener("click", (event) => {
    const viewButton = event.target.closest?.(".broadcast-view");
    if (viewButton) {
      const id = Number(viewButton.dataset.id || 0);
      if (id) {
        currentBroadcastId = id;
        window.setTimeout(() => refreshBroadcastDetail(id, { quiet: true }), 800);
      }
      return;
    }

    const reloadButton = event.target.closest?.("#reloadBroadcasts");
    if (reloadButton && currentBroadcastId) {
      window.setTimeout(() => refreshBroadcastDetail(currentBroadcastId, { quiet: true }), 500);
    }
  });

  const detail = document.querySelector("#broadcastDetail");
  if (detail) {
    const observer = new MutationObserver(() => {
      const heading = detail.querySelector("h2")?.textContent || "";
      const match = heading.match(/#(\d+)/);
      if (match) currentBroadcastId = Number(match[1]);
    });
    observer.observe(detail, { childList: true, subtree: true });
  }

  window.setInterval(() => {
    const section = document.querySelector("#section-broadcasts");
    if (!currentBroadcastId || document.hidden || !section?.classList.contains("active")) return;
    refreshBroadcastDetail(currentBroadcastId, { quiet: true });
  }, 3000);
})();
