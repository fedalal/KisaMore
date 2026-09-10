(() => {
  const adminUserIds = new Set();
  let loadingAdmins = false;

  function ensureHeader() {
    const row = document.querySelector("#section-users thead tr");
    if (!row || row.querySelector("th[data-telegram-admin-column]")) return;
    const th = document.createElement("th");
    th.dataset.telegramAdminColumn = "1";
    th.textContent = "Telegram-админ";
    row.insertBefore(th, row.lastElementChild);
  }

  function decorateRows() {
    ensureHeader();
    document.querySelectorAll("#usersBody tr").forEach((row) => {
      if (row.querySelector("td[data-telegram-admin-cell]")) return;
      const giftButton = row.querySelector(".gift-button[data-user-id]");
      if (!giftButton) return;
      const userId = Number(giftButton.dataset.userId);
      if (!Number.isFinite(userId)) return;

      const td = document.createElement("td");
      td.dataset.telegramAdminCell = "1";
      const enabled = adminUserIds.has(userId);
      td.innerHTML = enabled
        ? `<div><span class="badge green">Админ</span></div><button type="button" class="telegram-admin-toggle" data-user-id="${userId}" data-enabled="0">Снять</button>`
        : `<button type="button" class="telegram-admin-toggle" data-user-id="${userId}" data-enabled="1">Сделать админом</button>`;
      row.insertBefore(td, row.lastElementChild);
    });

    document.querySelectorAll(".telegram-admin-toggle").forEach((button) => {
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
          document.querySelectorAll("#usersBody td[data-telegram-admin-cell]").forEach((cell) => cell.remove());
          decorateRows();
        } catch (error) {
          button.disabled = false;
          toast(`Ошибка: ${error.message}`);
        }
      });
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

  const body = document.querySelector("#usersBody");
  if (body) {
    new MutationObserver(() => {
      decorateRows();
      if (!adminUserIds.size) loadTelegramAdmins();
    }).observe(body, { childList: true });
  }

  document.querySelectorAll('.nav-item[data-section="users"]').forEach((button) => {
    button.addEventListener("click", () => setTimeout(loadTelegramAdmins, 0));
  });

  ensureHeader();
  setTimeout(loadTelegramAdmins, 500);
})();
