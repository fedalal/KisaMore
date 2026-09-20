(() => {
  "use strict";

  if (typeof titles === "undefined" || typeof selectSection !== "function" || typeof api !== "function") return;

  titles.broadcasts = ["Рассылки", "Новости, объявления, опросы и голосования в Telegram"];

  const LANGUAGE_NAMES = {
    all: "Все языки",
    ru: "Русский",
    en: "English",
    de: "Deutsch",
    fr: "Français",
    es: "Español",
    it: "Italiano",
    pt: "Português",
    pl: "Polski",
    zh: "中文",
  };
  const STATUS_NAMES = {
    pending: "В очереди",
    sending: "Отправляется",
    completed: "Завершена",
    cancelled: "Отменена",
  };
  const MODE_NAMES = {
    none: "Обычное сообщение",
    single: "Опрос · один ответ",
    multiple: "Опрос · несколько ответов",
  };

  const style = document.createElement("style");
  style.textContent = `
    .broadcast-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(320px,.85fr);gap:18px;align-items:start}
    .broadcast-form{display:grid;gap:14px}.broadcast-form label{display:grid;gap:7px;font-weight:600}
    .broadcast-form textarea{resize:vertical;min-height:110px}.broadcast-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .broadcast-poll{display:grid;gap:12px;padding:14px;border:1px solid var(--border,#dde3ea);border-radius:12px;background:rgba(127,127,127,.04)}
    .broadcast-actions{display:flex;gap:10px;flex-wrap:wrap}.broadcast-preview{border:1px solid var(--border,#dde3ea);border-radius:14px;padding:14px;min-height:120px}
    .broadcast-preview img,.broadcast-preview video{display:block;max-width:100%;max-height:320px;border-radius:12px;margin-bottom:12px}.broadcast-preview-text{white-space:pre-wrap;line-height:1.45}
    .broadcast-preview-option{display:block;width:100%;margin-top:7px;padding:9px 10px;border:1px solid var(--border,#dde3ea);border-radius:9px;text-align:center;background:transparent}
    .broadcast-detail{margin-top:18px}.broadcast-detail-photo{max-width:420px;max-height:320px;border-radius:12px;display:block;margin:12px 0}
    .broadcast-results{display:grid;gap:8px;margin-top:12px}.broadcast-result{display:grid;grid-template-columns:minmax(120px,1fr) auto auto;gap:10px;align-items:center;padding:9px 0;border-bottom:1px solid var(--border,#e5e7eb)}
    .broadcast-message{white-space:pre-wrap;line-height:1.45}.broadcast-small{font-size:12px;opacity:.7}.broadcast-check{display:flex!important;grid-template-columns:auto 1fr!important;align-items:center;gap:8px!important;font-weight:500!important}
    @media(max-width:1050px){.broadcast-grid{grid-template-columns:1fr}.broadcast-row{grid-template-columns:1fr}}
  `;
  document.head.append(style);

  const nav = document.querySelector(".sidebar nav");
  const anchor = document.querySelector('.nav-item[data-section="stars"]') || document.querySelector('.nav-item[data-section="users"]');
  if (!nav || !anchor || document.querySelector('.nav-item[data-section="broadcasts"]')) return;

  const button = document.createElement("button");
  button.className = "nav-item";
  button.dataset.section = "broadcasts";
  button.textContent = "📣 Рассылки";
  anchor.after(button);

  const section = document.createElement("section");
  section.id = "section-broadcasts";
  section.className = "section";
  section.innerHTML = `
    <div class="broadcast-grid">
      <div class="panel">
        <div class="panel-head"><div><h2>Новая рассылка</h2><p>Сообщение отправится активным пользователям выбранного языка.</p></div></div>
        <form id="broadcastForm" class="broadcast-form">
          <div class="broadcast-row">
            <label>Язык получателей
              <select id="broadcastLanguage"></select>
            </label>
            <label>Тип сообщения
              <select id="broadcastMode">
                <option value="none">Обычное сообщение</option>
                <option value="single">Опрос · один ответ</option>
                <option value="multiple">Опрос · несколько ответов</option>
              </select>
            </label>
          </div>
          <div id="broadcastAudienceNote" class="watering-note">Загрузка аудитории…</div>
          <label>Текст сообщения
            <textarea id="broadcastText" maxlength="3500" rows="8" placeholder="Новость, объявление или пояснение к опросу"></textarea>
          </label>
          <label>Медиа (необязательно)
            <input id="broadcastMedia" type="file" accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm,video/quicktime">
            <span class="broadcast-small">Фото — до 2 МБ. Видео и GIF — до 100 МБ. Большие GIF/видео автоматически оптимизируются перед отправкой в Telegram.</span>
          </label>
          <div id="broadcastPollFields" class="broadcast-poll" hidden>
            <label>Вопрос
              <textarea id="broadcastQuestion" maxlength="500" rows="3" placeholder="Например: Какую культуру вы хотели бы выращивать следующей?"></textarea>
            </label>
            <label>Варианты ответа — по одному в строке
              <textarea id="broadcastOptions" rows="7" placeholder="Базилик\nМята\nКлубника\nОстрый перец"></textarea>
            </label>
            <label class="broadcast-check"><input id="broadcastShowResults" type="checkbox"> <span>Разрешить пользователям посмотреть текущие результаты</span></label>
            <div class="broadcast-small">От 2 до 10 вариантов. В режиме «несколько ответов» пользователь может выбрать несколько кнопок.</div>
          </div>
          <div class="broadcast-actions">
            <button id="broadcastPreviewButton" type="button">Предварительный просмотр</button>
            <button type="submit" class="primary">Отправить рассылку</button>
          </div>
        </form>
      </div>

      <div class="panel">
        <div class="panel-head"><div><h2>Предпросмотр</h2><p>Так будет выглядеть содержимое сообщения.</p></div></div>
        <div id="broadcastPreview" class="broadcast-preview"><div class="muted">Заполните сообщение и нажмите «Предварительный просмотр».</div></div>
      </div>
    </div>

    <div class="panel" style="margin-top:18px">
      <div class="panel-head">
        <div><h2>История рассылок</h2><p>Доставка, ошибки и ответы пользователей.</p></div>
        <button id="reloadBroadcasts">Обновить</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Дата</th><th>Аудитория</th><th>Тип</th><th>Доставка</th><th>Ответили</th><th>Статус</th><th></th></tr></thead>
          <tbody id="broadcastsBody"></tbody>
        </table>
      </div>
      <div id="broadcastDetail" class="broadcast-detail" hidden></div>
    </div>`;

  const rentalsSection = document.querySelector("#section-rentals");
  if (rentalsSection) rentalsSection.after(section);
  else document.querySelector(".content")?.append(section);

  let audience = { total: 0, languages: [], other: 0 };
  let previewUrl = null;

  function selectedAudienceCount() {
    const code = document.querySelector("#broadcastLanguage")?.value || "all";
    if (code === "all") return Number(audience.total || 0);
    return Number((audience.languages || []).find((item) => item.code === code)?.count || 0);
  }

  function updateAudienceNote() {
    const note = document.querySelector("#broadcastAudienceNote");
    if (!note) return;
    const code = document.querySelector("#broadcastLanguage")?.value || "all";
    const count = selectedAudienceCount();
    note.textContent = `${LANGUAGE_NAMES[code] || code}: ${count.toLocaleString("ru-RU")} активных получателей.`;
  }

  async function loadAudience() {
    audience = await api("/api/v1/admin/telegram-broadcasts/audience");
    const select = document.querySelector("#broadcastLanguage");
    if (!select) return;
    const previous = select.value || "ru";
    const rows = [{ code: "all", count: audience.total }, ...(audience.languages || [])];
    select.innerHTML = rows.map((item) =>
      `<option value="${esc(item.code)}">${esc(LANGUAGE_NAMES[item.code] || item.code)} — ${Number(item.count || 0).toLocaleString("ru-RU")}</option>`
    ).join("");
    select.value = rows.some((item) => item.code === previous) ? previous : "ru";
    updateAudienceNote();
  }

  function pollOptions() {
    const raw = document.querySelector("#broadcastOptions")?.value || "";
    const seen = new Set();
    const result = [];
    raw.split(/\r?\n/).forEach((line) => {
      const value = line.trim();
      const key = value.toLocaleLowerCase();
      if (value && !seen.has(key)) {
        seen.add(key);
        result.push(value);
      }
    });
    return result;
  }

  function togglePollFields() {
    const mode = document.querySelector("#broadcastMode")?.value || "none";
    const fields = document.querySelector("#broadcastPollFields");
    if (fields) fields.hidden = mode === "none";
  }

  function mediaLabel(file) {
    if (!file) return "";
    if (file.type === "image/gif") return "GIF-анимация";
    if (file.type.startsWith("video/")) return "видео";
    return "фотография";
  }

  function renderPreview() {
    const preview = document.querySelector("#broadcastPreview");
    if (!preview) return;
    const text = document.querySelector("#broadcastText")?.value.trim() || "";
    const question = document.querySelector("#broadcastQuestion")?.value.trim() || "";
    const mode = document.querySelector("#broadcastMode")?.value || "none";
    const options = mode === "none" ? [] : pollOptions();
    const file = document.querySelector("#broadcastMedia")?.files?.[0] || null;

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      previewUrl = null;
    }

    let media = "";
    if (file) {
      previewUrl = URL.createObjectURL(file);
      if (file.type.startsWith("video/")) {
        media = `<video class="broadcast-detail-photo" src="${previewUrl}" controls muted loop playsinline></video>`;
      } else {
        media = `<img src="${previewUrl}" alt="Предпросмотр медиа">`;
      }
    }

    const body = text ? `<div class="broadcast-preview-text">${esc(text)}</div>` : "";
    const poll = question ? `<div class="broadcast-preview-text" style="margin-top:12px"><strong>${esc(question)}</strong></div>` : "";
    const buttons = options.map((item) => `<span class="broadcast-preview-option">${esc(item)}</span>`).join("");
    preview.innerHTML = media || body || poll || buttons
      ? `${media}${body}${poll}${buttons}`
      : '<div class="muted">Сообщение пока пустое.</div>';
  }

  function validateForm() {
    const mode = document.querySelector("#broadcastMode")?.value || "none";
    const text = document.querySelector("#broadcastText")?.value.trim() || "";
    const question = document.querySelector("#broadcastQuestion")?.value.trim() || "";
    const media = document.querySelector("#broadcastMedia")?.files?.[0] || null;
    const options = mode === "none" ? [] : pollOptions();

    if (!text && !question && !media) throw new Error("Добавьте текст, вопрос или медиа.");
    if (mode !== "none" && !question) throw new Error("Для опроса нужен вопрос.");
    if (mode !== "none" && (options.length < 2 || options.length > 10)) throw new Error("Укажите от 2 до 10 вариантов ответа.");

    if (media) {
      const allowed = new Set([
        "image/jpeg", "image/png", "image/webp", "image/gif",
        "video/mp4", "video/webm", "video/quicktime",
      ]);
      if (!allowed.has(media.type)) {
        throw new Error("Поддерживаются JPEG, PNG, WEBP, GIF, MP4, MOV и WEBM.");
      }
      const maxBytes = (media.type === "image/gif" || media.type.startsWith("video/"))
        ? 100 * 1024 * 1024
        : 2 * 1024 * 1024;
      if (media.size > maxBytes) {
        throw new Error(
          media.type === "image/gif" || media.type.startsWith("video/")
            ? "Видео или GIF не должны превышать 100 МБ."
            : "Фотография не должна превышать 2 МБ."
        );
      }
    }

    return { mode, text, question, media, options };
  }

  async function submitBroadcast(event) {
    event.preventDefault();
    const formEl = event.currentTarget;
    try {
      const values = validateForm();
      const language = document.querySelector("#broadcastLanguage")?.value || "all";
      const count = selectedAudienceCount();
      const type = MODE_NAMES[values.mode] || values.mode;
      const mediaText = values.media ? ` + ${mediaLabel(values.media)}` : "";
      if (!window.confirm(`Отправить «${type}»${mediaText} аудитории «${LANGUAGE_NAMES[language] || language}»?\n\nПолучателей: ${count}`)) return;

      const form = new FormData();
      form.append("language_code", language);
      form.append("text", values.text);
      form.append("question", values.mode === "none" ? "" : values.question);
      form.append("answer_mode", values.mode);
      form.append("options_json", JSON.stringify(values.options));
      form.append("show_results_to_users", document.querySelector("#broadcastShowResults")?.checked ? "true" : "false");
      if (values.media) form.append("media", values.media);

      const submit = formEl.querySelector('button[type="submit"]');
      if (submit) submit.disabled = true;
      const result = await api("/api/v1/admin/telegram-broadcasts", { method: "POST", body: form });
      toast(`Рассылка #${result.id} поставлена в очередь для ${result.total_recipients} получателей.`);
      formEl.reset();
      document.querySelector("#broadcastLanguage").value = language;
      togglePollFields();
      updateAudienceNote();
      renderPreview();
      await loadBroadcasts();
      await showBroadcast(result.id);
      if (submit) submit.disabled = false;
    } catch (error) {
      formEl.querySelector('button[type="submit"]')?.removeAttribute("disabled");
      toast(`Ошибка: ${error.message}`);
    }
  }

  function statusBadge(status) {
    const cls = status === "completed" ? "green" : status === "cancelled" ? "red" : "";
    return `<span class="badge ${cls}">${esc(STATUS_NAMES[status] || status)}</span>`;
  }

  async function loadBroadcasts() {
    const body = document.querySelector("#broadcastsBody");
    if (!body) return;
    body.innerHTML = '<tr><td colspan="7" class="muted">Загрузка…</td></tr>';
    try {
      const rows = await api("/api/v1/admin/telegram-broadcasts?limit=100");
      body.innerHTML = rows.length ? rows.map((item) => {
        const delivered = `${Number(item.sent_count || 0).toLocaleString("ru-RU")} / ${Number(item.total_recipients || 0).toLocaleString("ru-RU")}`;
        const failed = item.failed_count ? `<div class="username">Ошибок: ${esc(item.failed_count)}</div>` : "";
        const answered = item.answer_mode === "none" ? "—" : `${Number(item.answered_users || 0).toLocaleString("ru-RU")} (${Number(item.response_rate || 0).toFixed(1)}%)`;
        const cancel = ["pending", "sending"].includes(item.status) ? `<button class="broadcast-cancel danger" data-id="${item.id}">Отменить</button>` : "";
        return `<tr>
          <td>${esc(fmtDate(item.created_at))}</td>
          <td><div class="user-name">${esc(LANGUAGE_NAMES[item.language_code] || item.language_code)}</div><div class="username">${esc(item.total_recipients)} получателей</div></td>
          <td>${esc(MODE_NAMES[item.answer_mode] || item.answer_mode)}${item.has_media ? `<div class="username">${item.media_kind === "animation" ? "🎞 GIF" : item.media_kind === "video" ? "🎬 Видео" : "📷 Фото"}</div>` : ""}</td>
          <td>${esc(delivered)}${failed}</td>
          <td>${esc(answered)}</td>
          <td>${statusBadge(item.status)}</td>
          <td><div class="table-actions"><button class="broadcast-view" data-id="${item.id}">Открыть</button>${cancel}</div></td>
        </tr>`;
      }).join("") : '<tr><td colspan="7" class="muted">Рассылок пока нет.</td></tr>';

      body.querySelectorAll(".broadcast-view").forEach((el) => el.addEventListener("click", () => showBroadcast(Number(el.dataset.id))));
      body.querySelectorAll(".broadcast-cancel").forEach((el) => el.addEventListener("click", async () => {
        if (!window.confirm(`Отменить рассылку #${el.dataset.id}? Уже отправленные сообщения останутся у пользователей.`)) return;
        el.disabled = true;
        try {
          await api(`/api/v1/admin/telegram-broadcasts/${el.dataset.id}/cancel`, { method: "POST" });
          toast("Рассылка отменена.");
          await loadBroadcasts();
          await showBroadcast(Number(el.dataset.id));
        } catch (error) {
          el.disabled = false;
          toast(`Ошибка: ${error.message}`);
        }
      }));
    } catch (error) {
      body.innerHTML = `<tr><td colspan="7" class="muted">Ошибка: ${esc(error.message)}</td></tr>`;
    }
  }

  async function showBroadcast(id) {
    const detail = document.querySelector("#broadcastDetail");
    if (!detail) return;
    detail.hidden = false;
    detail.innerHTML = '<div class="muted">Загрузка рассылки…</div>';
    try {
      const item = await api(`/api/v1/admin/telegram-broadcasts/${id}`);
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
      const results = item.options?.length ? `<div class="broadcast-results">${item.options.map((option) =>
        `<div class="broadcast-result"><strong>${esc(option.text)}</strong><span>${Number(option.vote_count || 0).toLocaleString("ru-RU")}</span><span>${Number(option.percentage_of_respondents || 0).toFixed(1)}%</span></div>`
      ).join("")}</div>` : "";
      detail.innerHTML = `
        <div class="panel-head"><div><h2>Рассылка #${esc(item.id)}</h2><p>${esc(LANGUAGE_NAMES[item.language_code] || item.language_code)} · ${esc(MODE_NAMES[item.answer_mode] || item.answer_mode)} · ${esc(fmtDate(item.created_at))}</p></div>${statusBadge(item.status)}</div>
        <div class="watering-note">Получателей: ${esc(item.total_recipients)} · отправлено: ${esc(item.sent_count)} · ошибок: ${esc(item.failed_count)}${item.answer_mode !== "none" ? ` · ответили: ${esc(item.answered_users)} (${Number(item.response_rate || 0).toFixed(1)}%)` : ""}</div>
        ${media}${text}${question}${results}`;
    } catch (error) {
      detail.innerHTML = `<div class="muted">Ошибка: ${esc(error.message)}</div>`;
    }
  }

  button.addEventListener("click", async () => {
    selectSection("broadcasts");
    try {
      await Promise.all([loadAudience(), loadBroadcasts()]);
    } catch (error) {
      toast(`Ошибка: ${error.message}`);
    }
  });
  document.querySelector("#broadcastLanguage")?.addEventListener("change", updateAudienceNote);
  document.querySelector("#broadcastMode")?.addEventListener("change", () => { togglePollFields(); renderPreview(); });
  document.querySelector("#broadcastPreviewButton")?.addEventListener("click", renderPreview);
  document.querySelector("#broadcastMedia")?.addEventListener("change", renderPreview);
  document.querySelector("#broadcastForm")?.addEventListener("submit", submitBroadcast);
  document.querySelector("#reloadBroadcasts")?.addEventListener("click", async () => {
    try { await Promise.all([loadAudience(), loadBroadcasts()]); } catch (error) { toast(`Ошибка: ${error.message}`); }
  });

  togglePollFields();
  window.loadTelegramBroadcasts = loadBroadcasts;
})();
