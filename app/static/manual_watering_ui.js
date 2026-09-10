(() => {
  "use strict";

  if (typeof cardHtml !== "function") return;

  cardHtml = function manualWateringCardHtml(r) {
    const lightToggle = toggleHtml(
      `t-light-${r.rack_id}`,
      r.light_mode === "manual",
      r.rack_id,
      "light"
    );

    return `
    <div class="card">
      <div class="card__head">
        <div>
          <div class="card__title">Стеллаж ${r.rack_id}</div>
          <div class="card__meta">💡 ${modeRu(r.light_mode)} · 💧 индивидуальный ручной полив</div>
        </div>
        ${cameraButtonHtml(r)}
        <button class="btn btn--ghost" onclick="openSchedule(${r.rack_id})">Расписание света</button>
      </div>

      <div class="badges">
        ${badge("Свет", "💡", r.light_on, r.light_mode, r.light_until, r.light_next)}
        <span class="badge ${r.water_on ? "badge--on" : "badge--off"}">
          <span class="ico">🚿</span>
          Сервисный клапан ${r.water_on ? "включен" : "выключен"}
        </span>
      </div>

      ${soilInfoHtml(r)}

      <div class="controls">
        <div class="controlRow">
          <div class="left">
            <div class="stack">
              <div class="label">💡 Свет</div>
              <div class="sub">Режим: ${lightToggle}</div>
            </div>
          </div>
          <div class="btns">
            <button class="btn ${r.light_on ? "btn--active" : ""}"
                    onclick="setManual(${r.rack_id}, 'light', true)">Вкл</button>
            <button class="btn ${!r.light_on ? "btn--active" : ""}"
                    onclick="setManual(${r.rack_id}, 'light', false)">Выкл</button>
          </div>
        </div>

        <div class="controlRow serviceWaterRow">
          <div class="left">
            <div class="stack">
              <div class="label">🚿 Сервисный клапан полива</div>
              <div class="sub">Растения поливаются индивидуально вручную. Здесь клапан включается только для обслуживания системы.</div>
            </div>
          </div>
          <div class="btns">
            <button class="btn ${r.water_on ? "btn--active" : ""}"
                    title="Сервисное включение полива всей полки"
                    onclick="setManual(${r.rack_id}, 'water', true)">Вкл</button>
            <button class="btn ${!r.water_on ? "btn--active" : ""}"
                    onclick="setManual(${r.rack_id}, 'water', false)">Выкл</button>
          </div>
        </div>
      </div>
    </div>`;
  };

  // The scheduling modal is now exclusively for lighting. Old water intervals
  // may remain in the database for history/compatibility, but the operator can
  // no longer edit or enable them from the UI.
  const waterTab = document.querySelector('.tab[data-tab="water"]');
  if (waterTab) waterTab.remove();
})();
