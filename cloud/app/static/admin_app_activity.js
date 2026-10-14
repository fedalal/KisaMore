/* KisaMore Battle — per-account Android activity. Uses authenticated admin API. */
let appActivityRequest = 0;
let appActivitySelected = null;

const activityActions = {
  launch: "Запуск приложения",
  screen: "Открыт экран",
  heartbeat: "Использование приложения",
  camera: "Переключение камеры",
  timelapse: "Просмотр таймлапса",
  error: "Ошибка приложения"
};
const activityScreens = {
  home:"Начало", battle:"Битва", history:"История", profile:"Профиль",
  login:"Вход", register:"Регистрация", viewer:"Просмотрщик",
  inbox:"Уведомления", other:"Другое"
};

async function loadAppActivity() {
  const id = ++appActivityRequest;
  const days = qs("#appActivityDays").value;
  qs("#appActivityError").textContent = "";
  try {
    const report = await api("/api/v1/admin/app-activity?days=" + days);
    if (id !== appActivityRequest) return;
    qs("#appActivityNote").textContent =
      "Часовой пояс: " + report.timezone + ". Обновлено: " + fmtDate(report.as_of) +
      ". Только версии Android с телеметрией. Участие в тестировании Google Play здесь не подтверждается.";
    const cards = [
      ["Пользователи и гости",report.tracked_people],
      ["Авторизованные аккаунты",report.tracked_accounts],
      ["Запуски",report.launches],
      ["Время использования, мин",report.minutes],
      ["События",report.events]
    ];
    qs("#appActivityCards").innerHTML = cards.map(([name,value]) =>
      '<div class="stat-card"><div class="label">' + esc(name) +
      '</div><div class="value">' + esc(value) + '</div></div>').join("");
    qs("#appActivityUsers").innerHTML = report.people.length ?
      report.people.map((person, i) => '<tr><td><strong>' + esc(person.name) +
        '</strong><div class="muted">' + esc(person.email || "Гостевая установка") + '</div></td>' +
        '<td>' + esc(person.app_version) + '</td><td>' + esc(person.android_version) +
        '</td><td>' + esc(person.sessions) + '</td><td>' + esc(person.minutes) +
        '</td><td>' + esc(person.events) + '</td><td>' + esc(fmtDate(person.last_seen)) +
        '</td><td><button type="button" class="activity-user-button" data-index="' + i +
        '">Действия</button></td></tr>').join("") :
      '<tr><td colspan="8" class="muted">Пока нет данных. Они появятся после установки новой версии Android-приложения.</td></tr>';
    qsa(".activity-user-button").forEach(btn => btn.addEventListener("click", () =>
      loadPersonAppActivity(report.people[Number(btn.dataset.index)])));
    if (appActivitySelected) {
      const person = report.people.find(p => p.key === appActivitySelected);
      if (person) await loadPersonAppActivity(person);
      else qs("#appActivityDetailsPanel").hidden = true;
    }
  } catch (err) {
    if (id !== appActivityRequest) return;
    qs("#appActivityError").textContent = "Ошибка загрузки: " + err.message;
  }
}

async function loadPersonAppActivity(person) {
  appActivitySelected = person.key;
  const days = qs("#appActivityDays").value;
  const panel = qs("#appActivityDetailsPanel");
  panel.hidden = false;
  qs("#appActivityPerson").textContent = person.name;
  qs("#appActivityPersonDetails").textContent = person.email || "Гость · " + person.key.slice(-8);
  qs("#appActivityEvents").innerHTML = '<tr><td colspan="5">Загрузка…</td></tr>';
  try {
    const data = await api("/api/v1/admin/app-activity/events?days=" + days +
      "&key=" + encodeURIComponent(person.key) + "&limit=500");
    if (appActivitySelected !== person.key) return;
    qs("#appActivityEvents").innerHTML = data.events.length ?
      data.events.map(item =>
        '<tr><td>' + esc(fmtDate(item.time)) + '</td><td>' +
        esc(activityActions[item.kind] || item.kind) + '</td><td>' +
        esc(activityScreens[item.screen] || item.screen) + '</td><td>' +
        esc(item.kind === "heartbeat" ? item.seconds + " сек." : item.label || "—") +
        '</td><td>' + esc(item.app_version) + ' · Android ' +
        esc(item.android_version) + '</td></tr>').join("") :
      '<tr><td colspan="5" class="muted">Событий за выбранный период нет.</td></tr>';
    qs("#appActivityLimit").textContent = data.events.length >= 500 ?
      "Показаны последние 500 событий. Выберите более короткий период для подробностей." : "";
    panel.scrollIntoView({behavior:"smooth",block:"start"});
  } catch (err) {
    qs("#appActivityEvents").innerHTML = '<tr><td colspan="5">' +
      esc("Ошибка: " + err.message) + '</td></tr>';
  }
}
qs("#appActivityDays").addEventListener("change", loadAppActivity);
qs("#appActivityRefresh").addEventListener("click", loadAppActivity);
