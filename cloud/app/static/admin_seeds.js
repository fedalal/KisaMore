(() => {
  const seedNav = document.querySelector('[data-section="seeds"]');
  if (!seedNav) return;

  const fmtG = (value) => {
    const n = Number(value || 0);
    return `${n.toLocaleString("ru-RU", { maximumFractionDigits: 3 })} г`;
  };

  const statusBadge = (item) => {
    if (item.status === "unconfigured") return '<span class="badge red">Норма не задана</span>';
    if (item.status === "out") return '<span class="badge red">Нет для посадки</span>';
    if (item.status === "low") return '<span class="badge">Мало</span>';
    return '<span class="badge green">В наличии</span>';
  };

  function openSeeds(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    document.querySelectorAll(".section").forEach((el) => el.classList.toggle("active", el.id === "section-seeds"));
    document.querySelectorAll(".nav-item").forEach((el) => el.classList.toggle("active", el === seedNav));
    document.querySelector("#pageTitle").textContent = "Семена";
    document.querySelector("#pageSubtitle").textContent = "Остатки, приход, списание и нормы посева";
    loadSeeds();
  }

  async function loadSeeds() {
    const body = document.querySelector("#seedsBody");
    body.innerHTML = '<tr><td colspan="8" class="muted">Загрузка…</td></tr>';
    try {
      const rows = await api("/api/v1/admin/seeds");
      const available = rows.filter((item) => item.in_stock).length;
      const low = rows.filter((item) => item.status === "low").length;
      const unavailable = rows.filter((item) => !item.in_stock).length;
      document.querySelector("#seedSummary").innerHTML = [
        ["Растений с семенами", available],
        ["Малый остаток", low],
        ["Недоступны для аренды", unavailable],
      ].map(([label, value]) => `<div class="stat-card"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`).join("");

      body.innerHTML = rows.length ? rows.map((item) => `<tr>
        <td><div class="user-name">${esc(item.plant_name)}</div><div class="username">${esc(item.plant_code)}${item.plant_active ? "" : " · в архиве"}</div></td>
        <td>${statusBadge(item)}</td>
        <td><b>${esc(fmtG(item.balance_g))}</b></td>
        <td>${esc(fmtG(item.reserved_g))}<div class="username">${esc(item.reserved_plantings)} посевов</div></td>
        <td>${esc(fmtG(item.available_g))}</td>
        <td>${item.seed_rate_g > 0 ? `${esc(fmtG(item.seed_rate_g))} / контейнер` : '<span class="muted">Не задана</span>'}</td>
        <td><b>${esc(item.available_plantings)}</b></td>
        <td><div class="table-actions">
          <button class="seed-receipt primary" data-id="${esc(item.plant_id)}" data-name="${esc(item.plant_name)}">Приход</button>
          <button class="seed-writeoff" data-id="${esc(item.plant_id)}" data-name="${esc(item.plant_name)}">Списание</button>
          <button class="seed-rate" data-id="${esc(item.plant_id)}" data-name="${esc(item.plant_name)}" data-rate="${esc(item.seed_rate_g)}">Норма</button>
          <button class="seed-history" data-id="${esc(item.plant_id)}">История</button>
        </div></td>
      </tr>`).join("") : '<tr><td colspan="8" class="muted">Растения не найдены.</td></tr>';

      document.querySelectorAll(".seed-receipt, .seed-writeoff").forEach((button) => {
        button.addEventListener("click", () => {
          document.querySelector("#seedMovementPlantId").value = button.dataset.id;
          document.querySelector("#seedMovementPlantName").textContent = button.dataset.name;
          document.querySelector("#seedMovementType").value = button.classList.contains("seed-receipt") ? "receipt" : "writeoff";
          document.querySelector("#seedMovementAmount").value = "";
          document.querySelector("#seedMovementNote").value = "";
          document.querySelector("#seedMovementDialog").showModal();
          document.querySelector("#seedMovementAmount").focus();
        });
      });

      document.querySelectorAll(".seed-rate").forEach((button) => {
        button.addEventListener("click", () => {
          document.querySelector("#seedRatePlantId").value = button.dataset.id;
          document.querySelector("#seedRatePlantName").textContent = button.dataset.name;
          document.querySelector("#seedRateValue").value = Number(button.dataset.rate || 0) || "";
          document.querySelector("#seedRateDialog").showModal();
          document.querySelector("#seedRateValue").focus();
        });
      });

      document.querySelectorAll(".seed-history").forEach((button) => {
        button.addEventListener("click", () => loadSeedHistory(button.dataset.id));
      });
    } catch (error) {
      body.innerHTML = `<tr><td colspan="8" class="muted">Ошибка: ${esc(error.message)}</td></tr>`;
    }
  }

  async function submitMovement(event) {
    event.preventDefault();
    const plantId = document.querySelector("#seedMovementPlantId").value;
    const movementType = document.querySelector("#seedMovementType").value;
    const amount = Number(document.querySelector("#seedMovementAmount").value);
    const note = document.querySelector("#seedMovementNote").value.trim();
    try {
      await api(`/api/v1/admin/seeds/${encodeURIComponent(plantId)}/movements`, {
        method: "POST",
        body: JSON.stringify({ movement_type: movementType, amount_g: amount, note }),
      });
      document.querySelector("#seedMovementDialog").close();
      toast(movementType === "receipt" ? `Приход ${fmtG(amount)} записан.` : `Списание ${fmtG(amount)} записано.`);
      await loadSeeds();
    } catch (error) {
      toast(`Ошибка: ${error.message}`);
    }
  }

  async function submitRate(event) {
    event.preventDefault();
    const plantId = document.querySelector("#seedRatePlantId").value;
    const value = Number(document.querySelector("#seedRateValue").value);
    try {
      await api(`/api/v1/admin/seeds/${encodeURIComponent(plantId)}/rate`, {
        method: "PATCH",
        body: JSON.stringify({ seed_rate_g: value }),
      });
      document.querySelector("#seedRateDialog").close();
      toast(`Норма посева сохранена: ${fmtG(value)} на контейнер.`);
      await loadSeeds();
    } catch (error) {
      toast(`Ошибка: ${error.message}`);
    }
  }

  async function loadSeedHistory(plantId) {
    const body = document.querySelector("#seedHistoryBody");
    body.innerHTML = '<tr><td colspan="4" class="muted">Загрузка…</td></tr>';
    document.querySelector("#seedHistoryDialog").showModal();
    try {
      const data = await api(`/api/v1/admin/seeds/${encodeURIComponent(plantId)}/history?limit=100`);
      document.querySelector("#seedHistoryPlantName").textContent = data.plant_name;
      const labels = { receipt: "Приход", writeoff: "Списание", planting: "Посадка" };
      body.innerHTML = data.items.length ? data.items.map((item) => {
        const positive = Number(item.amount_g) > 0;
        const amount = `${positive ? "+" : "−"}${fmtG(Math.abs(Number(item.amount_g)))}`;
        const reference = item.reference_type === "planting" ? `Посадка ${item.reference_id}` : "";
        return `<tr>
          <td>${esc(fmtDate(item.created_at))}</td>
          <td>${esc(labels[item.movement_type] || item.movement_type)}</td>
          <td><b>${esc(amount)}</b></td>
          <td>${esc(item.note || reference || "—")} ${reference && item.note ? `<div class="username">${esc(reference)}</div>` : ""}</td>
        </tr>`;
      }).join("") : '<tr><td colspan="4" class="muted">Движений пока нет.</td></tr>';
    } catch (error) {
      body.innerHTML = `<tr><td colspan="4" class="muted">Ошибка: ${esc(error.message)}</td></tr>`;
    }
  }

  seedNav.addEventListener("click", openSeeds, true);
  document.querySelector("#reloadSeeds").addEventListener("click", loadSeeds);
  document.querySelector("#seedMovementForm").addEventListener("submit", submitMovement);
  document.querySelector("#seedRateForm").addEventListener("submit", submitRate);
  document.querySelectorAll("[data-close-seed-dialog]").forEach((button) => {
    button.addEventListener("click", () => document.querySelector(`#${button.dataset.closeSeedDialog}`).close());
  });
})();
