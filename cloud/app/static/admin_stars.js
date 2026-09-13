(() => {
  "use strict";

  if (typeof titles === "undefined" || typeof selectSection !== "function" || typeof api !== "function") return;

  titles.stars = ["Telegram Stars", "Платежи Stars, баланс бота и официальные операции Telegram"];

  const nav = document.querySelector(".sidebar nav");
  const usersButton = document.querySelector('.nav-item[data-section="users"]');
  if (!nav || !usersButton || document.querySelector('.nav-item[data-section="stars"]')) return;

  const button = document.createElement("button");
  button.className = "nav-item";
  button.dataset.section = "stars";
  button.textContent = "⭐ Telegram Stars";
  usersButton.after(button);

  const section = document.createElement("section");
  section.id = "section-stars";
  section.className = "section";
  section.innerHTML = `
    <div id="starsSummary" class="stat-grid"></div>

    <div class="panel">
      <div class="panel-head">
        <div>
          <h2>Покупки Ⓚ за Telegram Stars</h2>
          <p>Платежи, которые бот принял от пользователей и записал в базу KisaMore.</p>
        </div>
        <button id="reloadStars">Обновить</button>
      </div>
      <div id="starsSyncNote" class="watering-note">Загрузка данных Telegram Stars…</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Пользователь</th><th>Stars</th><th>Начислено</th><th>Дата</th><th>Telegram</th><th>ID платежа</th></tr></thead>
          <tbody id="starsPurchasesBody"></tbody>
        </table>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <div>
          <h2>Официальные операции Telegram</h2>
          <p>Зеркало getStarTransactions: поступления, возвраты, выводы и другие изменения реального Star-баланса бота.</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Дата</th><th>Операция</th><th>Stars</th><th>Партнёр</th><th>Тип</th><th>Transaction ID</th></tr></thead>
          <tbody id="starsOfficialBody"></tbody>
        </table>
      </div>
    </div>`;

  const usersSection = document.querySelector("#section-users");
  if (usersSection) usersSection.after(section);
  else document.querySelector(".content")?.append(section);

  const starValue = (value) => `⭐ ${Number(value || 0).toLocaleString("ru-RU")}`;
  const kisaValue = (value) => `Ⓚ ${Number(value || 0).toLocaleString("ru-RU")}`;

  function fullName(item) {
    return [item.first_name, item.last_name].filter(Boolean).join(" ") || "Без имени";
  }

  function purchaseState(value) {
    if (value === "confirmed") return '<span class="badge green">Подтверждено Telegram</span>';
    if (value === "refunded") return '<span class="badge red">Возврат / списание</span>';
    return '<span class="badge">Не в последних операциях</span>';
  }

  function transactionType(item) {
    const values = {
      invoice_payment: "Оплата счёта",
      paid_media_payment: "Платные медиа",
      gift_purchase: "Покупка подарка ботом",
      premium_purchase: "Telegram Premium",
      business_account_transfer: "Перевод business account",
    };
    return values[item.transaction_type] || item.transaction_type || item.partner_type || "—";
  }

  function partnerText(item) {
    if (item.telegram_user_id) {
      const name = fullName(item);
      const username = item.username ? `@${item.username}` : `Telegram ${item.telegram_user_id}`;
      return `<div class="user-name">${esc(name)}</div><div class="username">${esc(username)}</div>`;
    }
    const labels = {
      fragment: "Fragment",
      telegram_ads: "Telegram Ads",
      telegram_api: "Telegram API",
      affiliate_program: "Affiliate program",
      chat: "Telegram chat",
      other: "Другое",
    };
    return esc(labels[item.partner_type] || item.partner_type || "—");
  }

  async function loadTelegramStars() {
    const summaryEl = document.querySelector("#starsSummary");
    const noteEl = document.querySelector("#starsSyncNote");
    const purchasesEl = document.querySelector("#starsPurchasesBody");
    const officialEl = document.querySelector("#starsOfficialBody");
    if (!summaryEl || !noteEl || !purchasesEl || !officialEl) return;

    summaryEl.innerHTML = '<div class="stat-card"><div class="label">Telegram Stars</div><div class="value">Загрузка…</div></div>';
    try {
      const data = await api("/api/v1/admin/telegram-stars");
      const s = data.summary || {};
      const balance = s.official_balance == null ? "—" : starValue(s.official_balance);
      const cards = [
        ["Реальный баланс бота", balance],
        ["Получено всего", starValue(s.stars_received_all_time)],
        ["Получено сегодня", starValue(s.stars_received_today)],
        ["Получено в этом месяце", starValue(s.stars_received_month)],
        ["Начислено пользователям", kisaValue(s.kisa_issued_for_stars)],
        ["Успешных покупок", Number(s.payments_count || 0).toLocaleString("ru-RU")],
      ];
      summaryEl.innerHTML = cards.map(([label, value]) =>
        `<div class="stat-card"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`
      ).join("");

      if (s.official_sync_error) {
        noteEl.textContent = `⚠️ Последняя синхронизация с Telegram завершилась ошибкой: ${s.official_sync_error}`;
      } else if (s.official_synced_at) {
        noteEl.textContent = `Официальный баланс и операции получены напрямую от Telegram. Последняя синхронизация: ${fmtDate(s.official_synced_at)}. Статистика дня и месяца считается в часовом поясе ${s.timezone || "UTC"}.`;
      } else {
        noteEl.textContent = "Ожидаем первую синхронизацию Telegram-бота. Обычно она появляется в течение нескольких секунд после его запуска.";
      }

      const purchases = data.purchases || [];
      purchasesEl.innerHTML = purchases.length ? purchases.map((item) => {
        const username = item.username ? `@${item.username}` : `Telegram ${item.telegram_user_id}`;
        return `<tr>
          <td><div class="user-name">${esc(fullName(item))}</div><div class="username">${esc(username)}</div></td>
          <td class="balance">${esc(starValue(item.stars))}</td>
          <td class="balance">${esc(kisaValue(item.kisa))}</td>
          <td>${esc(fmtDate(item.paid_at))}</td>
          <td>${purchaseState(item.official_state)}</td>
          <td><code>${esc(item.telegram_payment_charge_id)}</code></td>
        </tr>`;
      }).join("") : '<tr><td colspan="6" class="muted">Покупок за Stars пока нет.</td></tr>';

      const official = data.official_transactions || [];
      officialEl.innerHTML = official.length ? official.map((item) => {
        const incoming = item.direction === "incoming";
        const direction = incoming ? '<span class="badge green">Поступление</span>' : item.direction === "outgoing" ? '<span class="badge red">Списание</span>' : '<span class="badge">Операция</span>';
        const amount = `${incoming ? "+" : item.direction === "outgoing" ? "−" : ""}⭐ ${Number(item.stars || 0).toLocaleString("ru-RU")}`;
        return `<tr>
          <td>${esc(fmtDate(item.occurred_at))}</td>
          <td>${direction}</td>
          <td class="balance">${esc(amount)}</td>
          <td>${partnerText(item)}</td>
          <td>${esc(transactionType(item))}</td>
          <td><code>${esc(item.transaction_id)}</code></td>
        </tr>`;
      }).join("") : '<tr><td colspan="6" class="muted">Официальные операции Telegram ещё не синхронизированы.</td></tr>';
    } catch (error) {
      summaryEl.innerHTML = '<div class="stat-card"><div class="label">Telegram Stars</div><div class="value">Ошибка</div></div>';
      noteEl.textContent = `Не удалось загрузить данные: ${error.message}`;
      purchasesEl.innerHTML = '<tr><td colspan="6" class="muted">Данные недоступны.</td></tr>';
      officialEl.innerHTML = '<tr><td colspan="6" class="muted">Данные недоступны.</td></tr>';
    }
  }

  button.addEventListener("click", () => {
    selectSection("stars");
    loadTelegramStars();
  });
  document.querySelector("#reloadStars")?.addEventListener("click", loadTelegramStars);

  window.loadTelegramStars = loadTelegramStars;
})();
