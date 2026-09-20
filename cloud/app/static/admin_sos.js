(() => {
  let currentReportId = null;
  let loading = false;

  function statusLabel(status) {
    if (status === "resolved") return ["Закрыто", "green"];
    if (status === "new") return ["Новое", "red"];
    return ["В работе", ""];
  }

  function threadUser(item) {
    const username = item.user?.username ? ` @${item.user.username}` : "";
    return `${item.user?.name || "Пользователь"}${username}`;
  }

  function renderThreads(rows) {
    const list = document.querySelector("#sosThreadList");
    if (!list) return;

    const unreadTotal = rows.reduce((sum, item) => sum + Number(item.unread || 0), 0);
    document.querySelectorAll('.nav-item[data-section="sos"]').forEach((button) => {
      button.textContent = unreadTotal ? `🚨 SOS (${unreadTotal})` : "🚨 SOS";
    });

    if (!rows.length) {
      list.innerHTML = '<div class="sos-empty">SOS-сообщений пока нет.</div>';
      return;
    }

    list.innerHTML = rows.map((item) => {
      const [status, cls] = statusLabel(item.status);
      const active = Number(item.id) === Number(currentReportId) ? " active" : "";
      const unread = Number(item.unread || 0)
        ? `<span class="sos-unread">${esc(item.unread)}</span>`
        : "";
      const sender = item.last_sender === "admin" ? "Админ: " : "";
      return `<button type="button" class="sos-thread-item${active}" data-sos-id="${item.id}">
        <div class="sos-thread-top">
          <div class="sos-thread-title">${esc(item.plant?.name || "Растение")}</div>
          <div style="display:flex;gap:6px;align-items:center">
            ${unread}
            <span class="badge ${cls}">${esc(status)}</span>
          </div>
        </div>
        <div class="sos-thread-meta">${esc(threadUser(item))} · Полка ${esc(item.plant?.rack_id)} / ${esc(item.plant?.slot_number)}</div>
        <div class="sos-thread-preview">${esc(sender + (item.last_message || ""))}</div>
        <div class="sos-thread-meta">${esc(fmtDate(item.last_at || item.created_at))}</div>
      </button>`;
    }).join("");

    list.querySelectorAll("[data-sos-id]").forEach((button) => {
      button.addEventListener("click", () => openThread(Number(button.dataset.sosId)));
    });
  }

  async function loadThreads({ keepSelection = true } = {}) {
    if (loading) return;
    loading = true;
    try {
      const rows = await api("/api/v1/admin/sos");
      renderThreads(rows);
      if (!keepSelection && rows.length) {
        await openThread(Number(rows[0].id), { reloadList: false });
      }
    } catch (error) {
      const list = document.querySelector("#sosThreadList");
      if (list) list.innerHTML = `<div class="error" style="padding:16px">${esc(error.message)}</div>`;
    } finally {
      loading = false;
    }
  }

  function renderThread(data) {
    currentReportId = Number(data.id);
    const empty = document.querySelector("#sosChatEmpty");
    const chat = document.querySelector("#sosChatActive");
    if (empty) empty.hidden = true;
    if (chat) chat.hidden = false;

    document.querySelector("#sosChatTitle").textContent =
      `${data.plant.name} · полка ${data.plant.rack_id} / контейнер ${data.plant.slot_number}`;
    const username = data.user.username ? `@${data.user.username}` : "без username";
    document.querySelector("#sosChatUser").textContent =
      `${data.user.name} · ${username} · Telegram ${data.user.telegram_user_id}`;

    const [status, cls] = statusLabel(data.status);
    const badge = document.querySelector("#sosChatStatus");
    badge.textContent = status;
    badge.className = `badge ${cls}`;

    const statusButton = document.querySelector("#sosStatusButton");
    if (data.status === "resolved") {
      statusButton.textContent = "Вернуть в работу";
      statusButton.dataset.status = "open";
    } else {
      statusButton.textContent = "Закрыть обращение";
      statusButton.dataset.status = "resolved";
    }

    const box = document.querySelector("#sosChatMessages");
    const messages = data.messages || [];
    box.innerHTML = messages.length ? messages.map((message) => {
      const isAdmin = message.sender === "admin";
      const delivery = isAdmin && message.delivery_status === "pending"
        ? " · отправляется…"
        : (isAdmin && message.delivery_status === "failed" ? " · ошибка доставки" : "");
      return `<div class="sos-message ${isAdmin ? "admin" : "user"}">
        <div class="sos-message-author">${isAdmin ? "Администратор" : "Пользователь"}</div>
        <div>${esc(message.body)}</div>
        <div class="sos-message-time">${esc(fmtDate(message.created_at))}${esc(delivery)}</div>
      </div>`;
    }).join("") : '<div class="sos-empty">Сообщений пока нет.</div>';
    box.scrollTop = box.scrollHeight;
  }

  async function openThread(reportId, { reloadList = true } = {}) {
    currentReportId = Number(reportId);
    try {
      const data = await api(`/api/v1/admin/sos/${encodeURIComponent(reportId)}`);
      renderThread(data);
      if (reloadList) await loadThreads();
    } catch (error) {
      toast(`Ошибка SOS: ${error.message}`);
    }
  }

  async function sendReply(event) {
    event.preventDefault();
    if (!currentReportId) return;
    const input = document.querySelector("#sosReplyText");
    const message = input.value.trim();
    if (!message) return;

    const submit = event.submitter;
    if (submit) submit.disabled = true;
    try {
      await api(`/api/v1/admin/sos/${encodeURIComponent(currentReportId)}/messages`, {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      input.value = "";
      toast("Ответ поставлен в очередь Telegram.");
      await openThread(currentReportId);
    } catch (error) {
      toast(`Ошибка отправки: ${error.message}`);
    } finally {
      if (submit) submit.disabled = false;
    }
  }

  async function changeStatus() {
    if (!currentReportId) return;
    const button = document.querySelector("#sosStatusButton");
    const status = button.dataset.status;
    button.disabled = true;
    try {
      await api(`/api/v1/admin/sos/${encodeURIComponent(currentReportId)}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      toast(status === "resolved" ? "SOS-обращение закрыто." : "SOS-обращение снова в работе.");
      await openThread(currentReportId);
    } catch (error) {
      toast(`Ошибка: ${error.message}`);
    } finally {
      button.disabled = false;
    }
  }

  document.querySelectorAll('.nav-item[data-section="sos"]').forEach((button) => {
    button.addEventListener("click", () => setTimeout(() => loadThreads({ keepSelection: true }), 0));
  });
  document.querySelector("#reloadSos")?.addEventListener("click", () => loadThreads());
  document.querySelector("#sosReplyForm")?.addEventListener("submit", sendReply);
  document.querySelector("#sosStatusButton")?.addEventListener("click", changeStatus);

  setInterval(() => {
    const section = document.querySelector("#section-sos");
    if (section?.classList.contains("active")) {
      loadThreads();
      if (currentReportId) openThread(currentReportId, { reloadList: false });
    }
  }, 7000);

  setTimeout(() => loadThreads(), 1000);
})();
