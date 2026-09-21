(() => {
  const audienceLabels = {
    new: "Новые",
    existing: "Существующие",
    all: "Все",
  };

  const statusLabels = {
    scheduled: ["Запланирована", ""],
    active: ["Активна", "green"],
    ended: ["Завершена", ""],
    paused: ["Приостановлена", "red"],
  };

  function isoDateLocal(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }

  function initDates() {
    const start = document.querySelector("#promotionStartDate");
    const end = document.querySelector("#promotionEndDate");
    if (!start || !end || start.value || end.value) return;
    const today = new Date();
    const last = new Date(today);
    last.setDate(last.getDate() + 6);
    start.value = isoDateLocal(today);
    end.value = isoDateLocal(last);
  }

  function formatDateOnly(value) {
    if (!value) return "—";
    const [year, month, day] = String(value).split("-").map(Number);
    if (!year || !month || !day) return value;
    return new Intl.DateTimeFormat("ru-RU", {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(new Date(year, month - 1, day));
  }

  function statusBadge(item) {
    const [label, cls] = statusLabels[item.status] || [item.status || "—", ""];
    return `<span class="badge ${cls}">${esc(label)}</span>`;
  }

  async function loadPromotions() {
    const body = document.querySelector("#promotionsBody");
    if (!body) return;
    body.innerHTML = '<tr><td colspan="8" class="muted">Загрузка…</td></tr>';

    try {
      const result = await api("/api/v1/admin/promotions");
      const timezone = result.timezone || "UTC";
      const timezoneNode = document.querySelector("#promotionTimezone");
      if (timezoneNode) timezoneNode.textContent = ` Даты считаются по часовому поясу ${timezone}.`;

      const items = result.items || [];
      body.innerHTML = items.length ? items.map((item) => {
        const failed = Number(item.failed_count || 0);
        const notified = Number(item.notified_count || 0);
        const granted = Number(item.grant_count || 0);
        const eligible = Number(item.eligible_count || 0);
        const notifyText = failed
          ? `<span class="badge red">${notified} отправлено · ${failed} ошибок</span>`
          : `${notified}`;

        return `<tr>
          <td>
            <div class="user-name">${esc(item.name)}</div>
            <div class="username" style="max-width:360px;white-space:normal">${esc(item.message)}</div>
          </td>
          <td>${esc(audienceLabels[item.audience] || item.audience)}</td>
          <td>
            ${esc(formatDateOnly(item.start_date))} — ${esc(formatDateOnly(item.end_date))}
            <div class="username">${esc(timezone)}</div>
          </td>
          <td class="balance">${esc(kisa(item.amount_kisa))}</td>
          <td>${statusBadge(item)}</td>
          <td>
            <b>${granted}</b>
            <div class="username">подходит сейчас: ${eligible}</div>
          </td>
          <td>${notifyText}</td>
          <td>
            <button
              type="button"
              class="promotion-toggle ${item.enabled ? "danger" : ""}"
              data-id="${item.id}"
              data-enabled="${item.enabled ? "0" : "1"}">
              ${item.enabled ? "Приостановить" : "Возобновить"}
            </button>
          </td>
        </tr>`;
      }).join("") : '<tr><td colspan="8" class="muted">Акций пока нет.</td></tr>';

      document.querySelectorAll(".promotion-toggle").forEach((button) => {
        button.addEventListener("click", async () => {
          const enabled = button.dataset.enabled === "1";
          const action = enabled ? "возобновить" : "приостановить";
          if (!window.confirm(`Точно ${action} эту акцию?`)) return;
          button.disabled = true;
          try {
            await api(`/api/v1/admin/promotions/${button.dataset.id}`, {
              method: "PATCH",
              body: JSON.stringify({ enabled }),
            });
            toast(enabled ? "Акция возобновлена." : "Акция приостановлена.");
            await loadPromotions();
            if (typeof loadOverview === "function") await loadOverview();
          } catch (error) {
            button.disabled = false;
            toast(`Ошибка: ${error.message}`);
          }
        });
      });
    } catch (error) {
      body.innerHTML = `<tr><td colspan="8" class="error">${esc(error.message)}</td></tr>`;
    }
  }

  async function submitPromotion(event) {
    event.preventDefault();
    const submit = event.submitter;
    if (submit) submit.disabled = true;

    const payload = {
      name: document.querySelector("#promotionName").value.trim(),
      audience: document.querySelector("#promotionAudience").value,
      start_date: document.querySelector("#promotionStartDate").value,
      end_date: document.querySelector("#promotionEndDate").value,
      amount_kisa: Number(document.querySelector("#promotionAmount").value),
      message: document.querySelector("#promotionMessage").value.trim(),
      enabled: true,
    };

    try {
      const result = await api("/api/v1/admin/promotions", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      toast(`Акция «${result.name}» создана. Бонус: ${kisa(result.amount_kisa)}.`);
      document.querySelector("#promotionForm").reset();
      document.querySelector("#promotionAmount").value = "10";
      initDates();
      await loadPromotions();
      if (typeof loadOverview === "function") await loadOverview();
    } catch (error) {
      toast(`Ошибка создания акции: ${error.message}`);
    } finally {
      if (submit) submit.disabled = false;
    }
  }

  const form = document.querySelector("#promotionForm");
  if (!form) return;

  form.addEventListener("submit", submitPromotion);
  document.querySelector("#reloadPromotions")?.addEventListener("click", loadPromotions);

  const name = document.querySelector("#promotionName");
  const message = document.querySelector("#promotionMessage");
  name?.addEventListener("change", () => {
    if (message && !message.value.trim() && name.value.trim()) {
      message.value = `Поздравляем участников акции «${name.value.trim()}»!`;
    }
  });

  document.querySelectorAll('.nav-item[data-section="promotions"]').forEach((button) => {
    button.addEventListener("click", () => setTimeout(loadPromotions, 0));
  });

  initDates();
})();
