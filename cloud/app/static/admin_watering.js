(() => {
  "use strict";

  const adminView = document.querySelector("#adminView");
  const nav = document.querySelector('.nav-item[data-section="watering"]');
  const section = document.querySelector("#section-watering");
  const body = document.querySelector("#wateringBody");
  const summary = document.querySelector("#wateringSummary");
  const dateInput = document.querySelector("#wateringDate");
  const pendingOnly = document.querySelector("#wateringPendingOnly");
  const reload = document.querySelector("#reloadWatering");
  if (!adminView || !nav || !section || !body || !summary || !dateInput || !pendingOnly || !reload) return;

  let previousOverdue = null;
  let lastData = null;
  let loading = false;

  function openSection(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    qsa(".section").forEach((el) => el.classList.toggle("active", el === section));
    qsa(".nav-item").forEach((el) => el.classList.toggle("active", el === nav));
    qs("#pageTitle").textContent = "Поливы";
    qs("#pageSubtitle").textContent = "Индивидуальный ручной полив контейнеров";
    loadWaterings();
  }

  function localParts(value) {
    const text = String(value || "");
    return {
      date: text.length >= 10 ? text.slice(0, 10) : "",
      time: text.length >= 16 ? text.slice(11, 16) : "—",
    };
  }

  function statusHtml(item) {
    if (item.status === "done") return `<span class="watering-status done">Выполнено</span>`;
    if (item.status === "skipped") return `<span class="watering-status skipped">Пропущено</span>`;
    if (item.overdue) return `<span class="watering-status overdue">Просрочено</span>`;
    return `<span class="watering-status">Ожидает</span>`;
  }

  function typeHtml(item) {
    return item.task_type === "extra"
      ? `<span class="watering-type extra">Дополнительный</span>`
      : `<span class="watering-type">Плановый</span>`;
  }

  function renderSummary(data) {
    const s = data.summary;
    summary.innerHTML = `
      <div class="watering-stat overdue"><div class="label">Просрочено</div><div class="value">${esc(s.overdue)}</div></div>
      <div class="watering-stat"><div class="label">Ожидают</div><div class="value">${esc(s.pending)}</div></div>
      <div class="watering-stat"><div class="label">Выполнено</div><div class="value">${esc(s.done)}</div></div>
      <div class="watering-stat"><div class="label">Всего в списке</div><div class="value">${esc(s.total)}</div></div>`;
    nav.textContent = s.pending > 0 ? `💧 Поливы · ${s.pending}` : "💧 Поливы";
    nav.classList.toggle("watering-nav-overdue", s.overdue > 0);
    qs("#wateringTimezone").textContent = `Время теплицы: ${data.timezone}`;

    if (s.overdue > 0 && (previousOverdue === null || s.overdue > previousOverdue)) {
      toast(`Требуется внимание: просроченных поливов — ${s.overdue}.`);
    }
    previousOverdue = s.overdue;
  }

  function renderRows(data) {
    let rows = data.tasks;
    if (pendingOnly.checked) rows = rows.filter((item) => item.status === "pending");
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="7" class="muted">На выбранную дату поливов нет.</td></tr>`;
      return;
    }

    let html = "";
    let group = "";
    for (const item of rows) {
      const local = localParts(item.scheduled_local);
      const nextGroup = `${local.date}|${local.time}|${item.rack_id}`;
      if (nextGroup !== group) {
        group = nextGroup;
        const dateLabel = local.date && local.date !== data.date ? ` · ${local.date}` : "";
        html += `<tr class="watering-group"><td colspan="7">${esc(local.time)}${esc(dateLabel)} · Полка ${esc(item.rack_id)}</td></tr>`;
      }
      const classes = ["watering-row", item.status, item.overdue ? "overdue" : "", item.task_type === "extra" ? "extra" : ""].filter(Boolean).join(" ");
      const adjustment = item.watering_adjustment_percent
        ? `<div class="watering-date-small">Коррекция пользователя: ${item.watering_adjustment_percent > 0 ? "+" : ""}${esc(item.watering_adjustment_percent)}%</div>`
        : "";
      const completed = item.completed_local ? `<div class="watering-date-small">${esc(localParts(item.completed_local).time)}</div>` : "";
      const actions = item.status === "pending"
        ? `<div class="watering-actions">
            <input class="watering-actual" data-id="${esc(item.id)}" type="number" min="1" max="5000" value="${esc(item.planned_ml)}" aria-label="Фактически мл">
            <span class="ml-suffix">мл</span>
            <button class="watering-done primary" data-id="${esc(item.id)}">✓ Выполнен</button>
            <button class="watering-skip" data-id="${esc(item.id)}">Пропустить</button>
          </div>`
        : `<span class="muted">${item.actual_ml ? `Фактически ${esc(item.actual_ml)} мл` : "—"}</span>`;
      html += `<tr class="${classes}">
        <td><div class="watering-time">${esc(local.time)}</div><div class="watering-date-small">${esc(local.date)}</div></td>
        <td>Полка ${esc(item.rack_id)} · контейнер ${esc(item.slot_number)}</td>
        <td><div class="user-name">${esc(item.plant_name)}</div>${adjustment}</td>
        <td><strong>${esc(item.planned_ml)} мл</strong></td>
        <td>${typeHtml(item)}</td>
        <td>${statusHtml(item)}${completed}</td>
        <td>${actions}</td>
      </tr>`;
    }
    body.innerHTML = html;

    qsa(".watering-done").forEach((button) => button.addEventListener("click", async () => {
      const input = qs(`.watering-actual[data-id="${CSS.escape(button.dataset.id)}"]`);
      const actualMl = Number(input?.value || 0);
      if (!actualMl) return;
      button.disabled = true;
      try {
        await api(`/api/v1/admin/watering/${encodeURIComponent(button.dataset.id)}/complete`, {
          method: "POST",
          body: JSON.stringify({ actual_ml: actualMl }),
        });
        toast(`Полив отмечен выполненным: ${actualMl} мл.`);
        await loadWaterings();
      } catch (error) {
        button.disabled = false;
        toast(`Ошибка: ${error.message}`);
      }
    }));

    qsa(".watering-skip").forEach((button) => button.addEventListener("click", async () => {
      const reason = window.prompt("Причина пропуска:", "");
      if (reason === null) return;
      button.disabled = true;
      try {
        await api(`/api/v1/admin/watering/${encodeURIComponent(button.dataset.id)}/skip`, {
          method: "POST",
          body: JSON.stringify({ reason }),
        });
        toast("Полив отмечен пропущенным.");
        await loadWaterings();
      } catch (error) {
        button.disabled = false;
        toast(`Ошибка: ${error.message}`);
      }
    }));
  }

  async function loadWaterings() {
    if (loading || adminView.hidden) return;
    loading = true;
    if (section.classList.contains("active")) {
      body.innerHTML = `<tr><td colspan="7" class="muted">Загрузка поливов…</td></tr>`;
    }
    try {
      const query = dateInput.value ? `?day=${encodeURIComponent(dateInput.value)}` : "";
      const data = await api(`/api/v1/admin/watering${query}`);
      lastData = data;
      if (!dateInput.value) dateInput.value = data.date;
      renderSummary(data);
      renderRows(data);
    } catch (error) {
      if (section.classList.contains("active")) {
        body.innerHTML = `<tr><td colspan="7" class="error">Не удалось загрузить поливы: ${esc(error.message)}</td></tr>`;
      }
    } finally {
      loading = false;
    }
  }

  window.loadWaterings = loadWaterings;
  nav.addEventListener("click", openSection, true);
  reload.addEventListener("click", loadWaterings);
  dateInput.addEventListener("change", loadWaterings);
  pendingOnly.addEventListener("change", () => { if (lastData) renderRows(lastData); });

  const authObserver = new MutationObserver(() => {
    if (!adminView.hidden) loadWaterings();
  });
  authObserver.observe(adminView, { attributes: true, attributeFilter: ["hidden"] });
  if (!adminView.hidden) loadWaterings();

  // Reminders remain active even while the administrator is looking at another
  // section. This keeps the pending badge and overdue warning up to date.
  setInterval(() => {
    if (!adminView.hidden && !document.hidden) loadWaterings();
  }, 60000);
})();
