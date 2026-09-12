(() => {
  const adminUserIds = new Set();
  let loadingAdmins = false;

  const DEFAULT_RENTAL_PROGRESS_TEXT =
    "Ваша заявка в работе. Семена подготовлены и сейчас находятся в тёплом тёмном месте — это необходимый этап для прорастания. Как только появятся первые ростки, мы перенесём контейнер в теплицу и пришлём следующее обновление.";

  function ensureHeader() {
    const row = document.querySelector("#section-users thead tr");
    if (!row || row.querySelector("th[data-telegram-admin-column]")) return;
    const th = document.createElement("th");
    th.dataset.telegramAdminColumn = "1";
    th.textContent = "Telegram-админ";
    row.insertBefore(th, row.lastElementChild);
  }

  function bindToggle(button) {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", async () => {
      const userId = Number(button.dataset.userId);
      const enabled = button.dataset.enabled === "1";
      button.disabled = true;
      try {
        await api(`/api/v1/admin/telegram-admins/${userId}`, {
          method: "PUT",
          body: JSON.stringify({ enabled }),
        });
        if (enabled) adminUserIds.add(userId);
        else adminUserIds.delete(userId);
        toast(enabled
          ? "Telegram-админ включён. Бот отправит ему проверочное сообщение."
          : "Права Telegram-админа сняты.");
        decorateRows();
      } catch (error) {
        button.disabled = false;
        toast(`Ошибка: ${error.message}`);
      }
    });
  }

  function ensureMessageHistoryDialog() {
    if (document.querySelector("#telegramMessageHistoryDialog")) return;

    const dialog = document.createElement("dialog");
    dialog.id = "telegramMessageHistoryDialog";
    dialog.innerHTML = `
      <div class="dialog-card" style="width:min(900px,92vw);max-height:82vh;overflow:auto">
        <div class="dialog-head">
          <div>
            <h3>Сообщения пользователю</h3>
            <p id="telegramMessageHistoryUser"></p>
          </div>
          <button type="button" class="icon-button" id="closeTelegramMessageHistory">×</button>
        </div>
        <div id="telegramMessageHistoryInfo" class="muted" style="margin-bottom:12px"></div>
        <div id="telegramMessageHistoryBody"><div class="muted">Загрузка…</div></div>
        <div class="dialog-actions"><button type="button" id="closeTelegramMessageHistoryBottom">Закрыть</button></div>
      </div>`;
    document.body.appendChild(dialog);

    document.querySelector("#closeTelegramMessageHistory").addEventListener("click", () => dialog.close());
    document.querySelector("#closeTelegramMessageHistoryBottom").addEventListener("click", () => dialog.close());
  }

  function messageTypeLabel(type) {
    const labels = {
      text: "Текст",
      photo: "Фото",
      video: "Видео",
      invoice: "Счёт",
      rental_approved: "Аренда одобрена",
      rental_rejected: "Аренда отклонена",
      rental_progress: "Статус аренды",
      watering_done: "Полив",
    };
    return labels[type] || type || "Сообщение";
  }

  async function openMessageHistory(button) {
    ensureMessageHistoryDialog();
    const dialog = document.querySelector("#telegramMessageHistoryDialog");
    const userId = Number(button.dataset.userId);
    const userName = button.dataset.userName || "Пользователь";
    document.querySelector("#telegramMessageHistoryUser").textContent = userName;
    document.querySelector("#telegramMessageHistoryInfo").textContent = "";
    document.querySelector("#telegramMessageHistoryBody").innerHTML = `<div class="muted">Загрузка…</div>`;
    dialog.showModal();

    try {
      const result = await api(`/api/v1/admin/telegram-users/${userId}/messages?limit=300`);
      const messages = result.messages || [];
      const info = document.querySelector("#telegramMessageHistoryInfo");
      if (result.complete_history_since) {
        info.textContent = `Полный журнал всех исходящих сообщений ведётся с ${fmtDate(result.complete_history_since)}. Более старые системные уведомления показаны, если они сохранились в прежней очереди уведомлений.`;
      } else {
        info.textContent = "Полный журнал исходящих сообщений начнёт заполняться после обновления Telegram-бота. Более старые системные уведомления показаны, если они сохранились в прежней очереди уведомлений.";
      }

      const body = document.querySelector("#telegramMessageHistoryBody");
      if (!messages.length) {
        body.innerHTML = `<div class="muted">Сохранённых сообщений для этого пользователя пока нет.</div>`;
        return;
      }

      body.innerHTML = `<div style="display:grid;gap:10px">${messages.map((item) => {
        const media = item.media_name ? `<div class="username">📎 ${esc(item.media_name)}</div>` : "";
        const text = item.text ? esc(item.text) : `<span class="muted">Без текста</span>`;
        return `<article style="border:1px solid #e2e8f0;border-radius:10px;padding:10px 12px;background:#fff">
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:7px">
            <strong>${esc(fmtDate(item.sent_at))}</strong>
            <span class="badge green">${esc(messageTypeLabel(item.message_type))}</span>
          </div>
          <div style="white-space:pre-wrap;line-height:1.45">${text}</div>
          ${media}
        </article>`;
      }).join("")}</div>`;
    } catch (error) {
      document.querySelector("#telegramMessageHistoryBody").innerHTML = `<div class="error">${esc(error.message)}</div>`;
    }
  }

  function decorateRows() {
    ensureHeader();
    ensureMessageHistoryDialog();
    document.querySelectorAll("#usersBody tr").forEach((row) => {
      const giftButton = row.querySelector(".gift-button[data-user-id]");
      if (!giftButton) return;
      const userId = Number(giftButton.dataset.userId);
      if (!Number.isFinite(userId)) return;

      const actionCell = giftButton.closest("td");
      if (actionCell && !row.querySelector(".telegram-message-history-button")) {
        let actionWrap = actionCell.querySelector(".telegram-user-actions");
        if (!actionWrap) {
          actionWrap = document.createElement("div");
          actionWrap.className = "table-actions telegram-user-actions";
          giftButton.replaceWith(actionWrap);
          actionWrap.appendChild(giftButton);
        }
        const historyButton = document.createElement("button");
        historyButton.type = "button";
        historyButton.className = "telegram-message-history-button";
        historyButton.textContent = "Сообщения";
        historyButton.dataset.userId = String(userId);
        historyButton.dataset.userName = giftButton.dataset.userName || "Пользователь";
        historyButton.addEventListener("click", () => openMessageHistory(historyButton));
        actionWrap.appendChild(historyButton);
      }

      let td = row.querySelector("td[data-telegram-admin-cell]");
      if (!td) {
        td = document.createElement("td");
        td.dataset.telegramAdminCell = "1";
        row.insertBefore(td, row.lastElementChild);
      }

      const enabled = adminUserIds.has(userId);
      td.innerHTML = enabled
        ? `<div><span class="badge green">Админ</span></div><button type="button" class="telegram-admin-toggle" data-user-id="${userId}" data-enabled="0">Снять</button>`
        : `<button type="button" class="telegram-admin-toggle" data-user-id="${userId}" data-enabled="1">Сделать админом</button>`;
      const button = td.querySelector(".telegram-admin-toggle");
      if (button) bindToggle(button);
    });
  }

  async function loadTelegramAdmins() {
    if (loadingAdmins) return;
    loadingAdmins = true;
    try {
      const rows = await api("/api/v1/admin/telegram-admins");
      adminUserIds.clear();
      rows.forEach((item) => adminUserIds.add(Number(item.user_id)));
      decorateRows();
    } catch (_) {
      // Authentication may still be starting; the next users-table mutation retries.
    } finally {
      loadingAdmins = false;
    }
  }

  function ensureRentalProgressDialog() {
    if (document.querySelector("#rentalProgressDialog")) return;

    const dialog = document.createElement("dialog");
    dialog.id = "rentalProgressDialog";
    dialog.innerHTML = `
      <form id="rentalProgressForm" class="dialog-card">
        <div class="dialog-head">
          <div>
            <h3>Обновление по аренде</h3>
            <p id="rentalProgressTitle"></p>
          </div>
          <button type="button" class="icon-button" id="closeRentalProgressDialog">×</button>
        </div>
        <input id="rentalProgressRequestId" type="hidden">
        <label>Фото
          <input id="rentalProgressPhoto" type="file" accept="image/jpeg,image/png,image/webp" required>
        </label>
        <label>Сообщение пользователю
          <textarea id="rentalProgressMessage" rows="6" maxlength="700" required></textarea>
        </label>
        <p class="muted">Фото и текст будут отправлены пользователю в Telegram. Текст можно изменить перед каждой отправкой.</p>
        <div class="dialog-actions">
          <button type="button" id="cancelRentalProgressDialog">Отмена</button>
          <button type="submit" class="primary">Отправить пользователю</button>
        </div>
      </form>`;
    document.body.appendChild(dialog);

    document.querySelector("#closeRentalProgressDialog").addEventListener("click", () => dialog.close());
    document.querySelector("#cancelRentalProgressDialog").addEventListener("click", () => dialog.close());
    document.querySelector("#rentalProgressForm").addEventListener("submit", submitRentalProgress);
  }

  function openRentalProgress(button) {
    ensureRentalProgressDialog();
    const requestId = button.dataset.requestId;
    const plant = button.dataset.plant || "Растение";
    const location = button.dataset.location || "";
    document.querySelector("#rentalProgressRequestId").value = requestId;
    document.querySelector("#rentalProgressTitle").textContent = `${plant}${location ? ` · ${location}` : ""}`;
    document.querySelector("#rentalProgressPhoto").value = "";
    document.querySelector("#rentalProgressMessage").value = DEFAULT_RENTAL_PROGRESS_TEXT;
    document.querySelector("#rentalProgressDialog").showModal();
  }

  function decorateRentalRows() {
    ensureRentalProgressDialog();
    document.querySelectorAll("#rentalsBody tr").forEach((row) => {
      if (row.querySelector(".rental-progress-button")) return;

      const sourceButton = row.querySelector(
        ".approve-rental[data-id], .reject-rental[data-id], .complete-rental[data-id]"
      );
      if (!sourceButton) return;

      const requestId = sourceButton.dataset.id;
      const cells = row.querySelectorAll("td");
      const plant = cells[1]?.querySelector(".user-name")?.textContent?.trim() || "Растение";
      const location = cells[2]?.childNodes?.[0]?.textContent?.trim() || "";
      const actionCell = cells[cells.length - 1];
      if (!actionCell) return;

      let actions = actionCell.querySelector(".table-actions");
      if (!actions) {
        actions = document.createElement("div");
        actions.className = "table-actions";
        actionCell.prepend(actions);
      }

      const button = document.createElement("button");
      button.type = "button";
      button.className = "rental-progress-button";
      button.textContent = "Фото + сообщение";
      button.dataset.requestId = requestId;
      button.dataset.plant = plant;
      button.dataset.location = location;
      button.addEventListener("click", () => openRentalProgress(button));
      actions.appendChild(button);
    });
  }

  async function submitRentalProgress(event) {
    event.preventDefault();
    const dialog = document.querySelector("#rentalProgressDialog");
    const requestId = document.querySelector("#rentalProgressRequestId").value;
    const photo = document.querySelector("#rentalProgressPhoto").files[0];
    const message = document.querySelector("#rentalProgressMessage").value.trim();
    if (!photo || !message) return;

    const submit = event.submitter;
    if (submit) submit.disabled = true;
    const form = new FormData();
    form.append("photo", photo);
    form.append("message", message);

    try {
      await api(`/api/v1/admin/rental-requests/${encodeURIComponent(requestId)}/progress`, {
        method: "POST",
        body: form,
      });
      dialog.close();
      toast("Фото и сообщение поставлены в очередь Telegram и будут отправлены в течение нескольких секунд.");
    } catch (error) {
      toast(`Ошибка отправки: ${error.message}`);
    } finally {
      if (submit) submit.disabled = false;
    }
  }

  const usersBody = document.querySelector("#usersBody");
  if (usersBody) {
    new MutationObserver(() => {
      decorateRows();
      if (!adminUserIds.size) loadTelegramAdmins();
    }).observe(usersBody, { childList: true });
  }

  const rentalsBody = document.querySelector("#rentalsBody");
  if (rentalsBody) {
    new MutationObserver(() => decorateRentalRows()).observe(rentalsBody, { childList: true });
  }

  document.querySelectorAll('.nav-item[data-section="users"]').forEach((button) => {
    button.addEventListener("click", () => setTimeout(loadTelegramAdmins, 0));
  });
  document.querySelectorAll('.nav-item[data-section="rentals"]').forEach((button) => {
    button.addEventListener("click", () => setTimeout(decorateRentalRows, 0));
  });

  ensureHeader();
  ensureMessageHistoryDialog();
  ensureRentalProgressDialog();
  setTimeout(loadTelegramAdmins, 500);
  setTimeout(decorateRentalRows, 500);
})();
