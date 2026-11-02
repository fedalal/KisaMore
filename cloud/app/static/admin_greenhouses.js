/* Greenhouse capacity controls. Does not change Raspberry Pi lighting or telemetry. */
async function loadGreenhouses() {
  const body = qs("#greenhousesBody");
  if (!body) return;
  body.innerHTML = '<tr><td colspan="7">Загрузка…</td></tr>';
  try {
    const items = await api("/api/v1/admin/greenhouses");
    const titles = {active:"Активна — принимает заказы", maintenance:"Модернизация", transport:"Перевозка", paused:"Приостановлена"};
    body.innerHTML = items.length ? items.map((item) => {
      const online = item.last_seen_at && (Date.now() - new Date(item.last_seen_at).getTime()) < 120000;
      return '<tr data-greenhouse-id="' + esc(item.device_id) + '">' +
        '<td><strong>' + esc(item.device_name) + '</strong><div class="muted">' + esc(item.device_id) + '</div></td>' +
        '<td>' + (item.racks_count || 0) + '</td>' +
        '<td>' + (online ? "🟢 На связи" : "⚪ Нет свежих данных") + '<div class="muted">' + esc(fmtDate(item.last_seen_at)) + '</div></td>' +
        '<td>' + item.active_allocations + '</td>' +
        '<td><select class="greenhouse-status" aria-label="Статус теплицы">' +
          Object.entries(titles).map(([key, title]) => '<option value="' + key + '"' + (key === item.status ? ' selected' : '') + '>' + title + '</option>').join("") +
        '</select></td>' +
        '<td><input class="greenhouse-note" maxlength="250" aria-label="Причина отключения" placeholder="Причина или комментарий" value="' + esc(item.note || "") + '"></td>' +
        '<td><button type="button" class="greenhouse-save">Сохранить</button></td>' +
        '</tr>';
    }).join("") : '<tr><td colspan="7">Теплицы пока не зарегистрированы.</td></tr>';
    qsa(".greenhouse-save").forEach(button => button.addEventListener("click", async () => {
      const row = button.closest("tr");
      const id = row.dataset.greenhouseId;
      const status = row.querySelector(".greenhouse-status").value;
      const note = row.querySelector(".greenhouse-note").value.trim();
      const original = items.find(item => item.device_id === id);
      if (status !== "active" && original?.active_allocations > 0 &&
          !window.confirm("В этой теплице есть действующие назначения. Они сохранятся, но новые заказы будут закрыты. Продолжить?")) return;
      button.disabled = true;
      try {
        await api("/api/v1/admin/greenhouses/" + encodeURIComponent(id), {
          method:"PATCH", body: JSON.stringify({status,note})
        });
        toast("Доступность теплицы обновлена");
        await loadGreenhouses();
      } catch (error) {
        toast("Ошибка: " + error.message);
        button.disabled = false;
      }
    }));
  } catch(error) {
    body.innerHTML = '<tr><td colspan="7">' + esc(error.message) + '</td></tr>';
  }
}
