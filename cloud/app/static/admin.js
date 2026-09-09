const qs = (s) => document.querySelector(s);
const qsa = (s) => [...document.querySelectorAll(s)];

const titles = {
  overview: ["Обзор", "Состояние KisaMore"],
  users: ["Пользователи", "Telegram-пользователи и баланс Kisa"],
  rentals: ["Заявки на аренду", "Подтверждение контейнеров и выбранных растений"],
  plantings: ["Растения и фото", "Активные посадки и публикация контента"],
  comments: ["Комментарии", "Модерация сообщества"],
};

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function fmtDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

function kisa(value) {
  return `Ⓚ ${Number(value || 0).toLocaleString("ru-RU")}`;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  if (response.status === 401) {
    showLogin();
    throw new Error("Требуется вход");
  }
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch (_) {}
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

function toast(message) {
  const el = qs("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => el.classList.remove("show"), 3000);
}

function showLogin(message = "") {
  qs("#adminView").hidden = true;
  qs("#loginView").hidden = false;
  qs("#loginError").textContent = message;
}

function showAdmin(me) {
  qs("#loginView").hidden = true;
  qs("#adminView").hidden = false;
  qs("#adminIdentity").textContent = `${me.display_name} · ${me.email}`;
}

async function checkSession() {
  try {
    const me = await api("/api/v1/auth/me");
    if (me.role !== "admin") {
      showLogin("У этой учётной записи нет прав администратора.");
      return;
    }
    showAdmin(me);
    await loadOverview();
  } catch (_) {
    showLogin();
  }
}

async function login(event) {
  event.preventDefault();
  qs("#loginError").textContent = "";
  try {
    const me = await api("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: qs("#loginEmail").value.trim(), password: qs("#loginPassword").value }),
    });
    if (me.role !== "admin") {
      showLogin("У этой учётной записи нет прав администратора.");
      return;
    }
    showAdmin(me);
    await loadOverview();
  } catch (error) {
    qs("#loginError").textContent = error.message === "Invalid email or password" ? "Неверный email или пароль." : error.message;
  }
}

async function logout() {
  try { await api("/api/v1/auth/logout", { method: "POST" }); } catch (_) {}
  showLogin();
}

function selectSection(name) {
  qsa(".section").forEach((el) => el.classList.toggle("active", el.id === `section-${name}`));
  qsa(".nav-item").forEach((el) => el.classList.toggle("active", el.dataset.section === name));
  qs("#pageTitle").textContent = titles[name][0];
  qs("#pageSubtitle").textContent = titles[name][1];
  if (name === "overview") loadOverview();
  if (name === "users") loadUsers();
  if (name === "rentals") loadRentals();
  if (name === "plantings") loadPlantings();
  if (name === "comments") loadComments();
}

async function loadOverview() {
  const data = await api("/api/v1/admin/overview");
  const cards = [
    ["Пользователи", data.telegram_users],
    ["Kisa в кошельках", kisa(data.total_kisa)],
    ["Активные растения", data.active_plantings],
    ["Комментарии", data.published_comments],
    ["Заявки на аренду", data.rental_requests],
  ];
  qs("#overviewCards").innerHTML = cards.map(([label, value]) => `<div class="stat-card"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`).join("");
}

async function loadUsers() {
  const query = qs("#userSearch").value.trim();
  const rows = await api(`/api/v1/admin/telegram-users?q=${encodeURIComponent(query)}`);
  qs("#usersBody").innerHTML = rows.length ? rows.map((user) => {
    const fullName = [user.first_name, user.last_name].filter(Boolean).join(" ") || "Без имени";
    const username = user.username ? `@${user.username}` : "—";
    return `<tr>
      <td><div class="user-name">${esc(fullName)}</div><div class="username">${esc(username)}</div></td>
      <td>${esc(user.telegram_user_id)}</td>
      <td>${esc(user.language_code || "—")}</td>
      <td class="balance">${esc(kisa(user.balance))}</td>
      <td>${esc(fmtDate(user.created_at))}</td>
      <td><button class="gift-button" data-user-id="${user.id}" data-user-name="${esc(fullName)}">Подарить Kisa</button></td>
    </tr>`;
  }).join("") : `<tr><td colspan="6" class="muted">Пользователи не найдены.</td></tr>`;

  qsa(".gift-button").forEach((button) => button.addEventListener("click", () => {
    qs("#giftUserId").value = button.dataset.userId;
    qs("#giftUserName").textContent = button.dataset.userName;
    qs("#giftAmount").value = "100";
    qs("#giftReason").value = "";
    qs("#giftDialog").showModal();
  }));
}

async function submitGift(event) {
  event.preventDefault();
  const id = Number(qs("#giftUserId").value);
  const amount = Number(qs("#giftAmount").value);
  const reason = qs("#giftReason").value.trim();
  try {
    const result = await api(`/api/v1/admin/telegram-users/${id}/gift-kisa`, {
      method: "POST",
      body: JSON.stringify({ amount, reason }),
    });
    qs("#giftDialog").close();
    toast(`Начислено ${kisa(amount)}. Новый баланс: ${kisa(result.balance)}`);
    await loadUsers();
    await loadOverview();
  } catch (error) {
    toast(`Ошибка: ${error.message}`);
  }
}

function rentalStatus(status) {
  const labels = { requested: "Ожидает", approved: "Одобрено", rejected: "Отклонено" };
  const cls = status === "approved" ? "green" : status === "rejected" ? "red" : "";
  return `<span class="badge ${cls}">${esc(labels[status] || status)}</span>`;
}

async function loadRentals() {
  const rows = await api("/api/v1/admin/rental-requests");
  qs("#rentalsBody").innerHTML = rows.length ? rows.map((item) => {
    const fullName = [item.first_name, item.last_name].filter(Boolean).join(" ") || "Без имени";
    const username = item.username ? `@${item.username}` : `Telegram ${item.telegram_user_id}`;
    const actions = item.status === "requested"
      ? `<div class="table-actions"><button class="approve-rental primary" data-id="${item.id}">Одобрить</button><button class="reject-rental danger" data-id="${item.id}">Отклонить</button></div>`
      : item.allocation_id
        ? `<span class="username">Назначение: ${esc(item.allocation_id)}</span>`
        : `<span class="muted">—</span>`;
    const note = item.note && item.status === "rejected" ? `<div class="username">${esc(item.note)}</div>` : "";
    const refund = item.refunded_at ? `<div class="username">Возвращено ${esc(kisa(item.price_kisa))}</div>` : "";
    return `<tr>
      <td><div class="user-name">${esc(fullName)}</div><div class="username">${esc(username)}</div></td>
      <td><div class="user-name">${esc(item.plant_name)}</div><div class="username">Аренда: ${esc(kisa(item.price_kisa))}</div></td>
      <td>Полка ${esc(item.rack_id)} · контейнер ${esc(item.slot_number)}<div class="username">${esc(item.device_id)}</div></td>
      <td>${esc(fmtDate(item.created_at))}</td>
      <td>${rentalStatus(item.status)}${note}${refund}</td>
      <td>${actions}</td>
    </tr>`;
  }).join("") : `<tr><td colspan="6" class="muted">Заявок на аренду пока нет.</td></tr>`;

  qsa(".approve-rental").forEach((button) => button.addEventListener("click", async () => {
    if (!window.confirm("Одобрить эту заявку и отправить назначение на Raspberry?")) return;
    button.disabled = true;
    try {
      const result = await api(`/api/v1/admin/rental-requests/${button.dataset.id}/approve`, { method: "POST" });
      toast(`Заявка одобрена. Allocation: ${result.allocation_id || "создан"}`);
      await loadRentals();
      await loadOverview();
    } catch (error) {
      button.disabled = false;
      toast(`Ошибка: ${error.message}`);
    }
  }));

  qsa(".reject-rental").forEach((button) => button.addEventListener("click", async () => {
    const reason = window.prompt("Причина отказа (можно оставить пустой):", "");
    if (reason === null) return;
    button.disabled = true;
    try {
      const result = await api(`/api/v1/admin/rental-requests/${button.dataset.id}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      const refundText = result.refunded_kisa > 0 ? ` Возвращено ${kisa(result.refunded_kisa)}.` : "";
      toast(`Заявка отклонена.${refundText} Контейнер снова доступен.`);
      await loadRentals();
      await loadOverview();
    } catch (error) {
      button.disabled = false;
      toast(`Ошибка: ${error.message}`);
    }
  }));
}

async function loadPlantings() {
  const rows = await api("/api/v1/admin/plantings");
  qs("#plantingsBody").innerHTML = rows.length ? rows.map((item) => `<tr>
    <td><div class="user-name">${esc(item.plant_name)}</div><div class="username">${esc(item.id)}</div></td>
    <td>Полка ${esc(item.rack_id)} · контейнер ${esc(item.slot_number)}</td>
    <td><span class="badge green">${esc(item.status)}</span></td>
    <td>${esc(fmtDate(item.planted_at))}</td>
    <td>${item.photo_url ? `<img class="thumb" src="${esc(item.photo_url)}?t=${Date.now()}" alt="Фото">` : `<span class="muted">Нет отдельного фото</span>`}</td>
    <td><button class="photo-button" data-id="${esc(item.id)}" data-name="${esc(item.plant_name)}">Опубликовать фото</button></td>
  </tr>`).join("") : `<tr><td colspan="6" class="muted">Активных посадок нет.</td></tr>`;

  qsa(".photo-button").forEach((button) => button.addEventListener("click", () => {
    qs("#photoPlantingId").value = button.dataset.id;
    qs("#photoPlantName").textContent = button.dataset.name;
    qs("#photoFile").value = "";
    qs("#photoCaption").value = "";
    qs("#photoDialog").showModal();
  }));
}

async function submitPhoto(event) {
  event.preventDefault();
  const id = qs("#photoPlantingId").value;
  const file = qs("#photoFile").files[0];
  if (!file) return;
  const form = new FormData();
  form.append("photo", file);
  form.append("caption", qs("#photoCaption").value.trim());
  try {
    await api(`/api/v1/admin/plantings/${encodeURIComponent(id)}/photo`, { method: "POST", body: form });
    qs("#photoDialog").close();
    toast("Фото опубликовано.");
    await loadPlantings();
  } catch (error) {
    toast(`Ошибка загрузки: ${error.message}`);
  }
}

async function loadComments() {
  const rows = await api("/api/v1/admin/comments");
  qs("#commentsBody").innerHTML = rows.length ? rows.map((item) => {
    const author = item.username ? `@${item.username}` : (item.first_name || "Без имени");
    const hidden = item.status === "hidden";
    return `<tr>
      <td>${esc(author)}</td>
      <td>${esc(item.body)}</td>
      <td>${esc(fmtDate(item.created_at))}</td>
      <td><span class="badge ${hidden ? "red" : "green"}">${esc(item.status)}</span></td>
      <td><button class="comment-status" data-id="${item.id}" data-status="${hidden ? "published" : "hidden"}">${hidden ? "Опубликовать" : "Скрыть"}</button></td>
    </tr>`;
  }).join("") : `<tr><td colspan="5" class="muted">Комментариев пока нет.</td></tr>`;

  qsa(".comment-status").forEach((button) => button.addEventListener("click", async () => {
    try {
      await api(`/api/v1/admin/comments/${button.dataset.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: button.dataset.status }),
      });
      toast("Статус комментария изменён.");
      await loadComments();
      await loadOverview();
    } catch (error) {
      toast(`Ошибка: ${error.message}`);
    }
  }));
}

qs("#loginForm").addEventListener("submit", login);
qs("#logoutButton").addEventListener("click", logout);
qsa(".nav-item").forEach((button) => button.addEventListener("click", () => selectSection(button.dataset.section)));
qs("#userSearchButton").addEventListener("click", loadUsers);
qs("#userSearch").addEventListener("keydown", (event) => { if (event.key === "Enter") loadUsers(); });
qs("#reloadRentals").addEventListener("click", loadRentals);
qs("#reloadPlantings").addEventListener("click", loadPlantings);
qs("#reloadComments").addEventListener("click", loadComments);
qs("#giftForm").addEventListener("submit", submitGift);
qs("#photoForm").addEventListener("submit", submitPhoto);
qsa("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => qs(`#${button.dataset.closeDialog}`).close()));

checkSession();
