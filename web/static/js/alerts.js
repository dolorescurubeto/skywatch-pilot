document.addEventListener("DOMContentLoaded", async () => {
  if (!requireAuth()) return;
  document.getElementById("logout-btn").addEventListener("click", logout);

  const user = getUser();
  const nameEl = document.getElementById("pilot-name");
  if (nameEl && user) nameEl.textContent = user.name || user.email;

  const list = document.getElementById("alerts-list");
  const empty = document.getElementById("alerts-empty");
  const historyList = document.getElementById("history-list");
  const historyEmpty = document.getElementById("history-empty");
  const viewActive = document.getElementById("view-active");
  const viewHistory = document.getElementById("view-history");
  const errorEl = document.getElementById("page-error");
  let currentView = "active";

  function typeBadge(type) {
    if (type === "OFFLINE" || type === "GEOFENCE_BREACH") {
      return `<span class="badge danger">${type}</span>`;
    }
    return `<span class="badge warn">${type}</span>`;
  }

  function setView(view) {
    currentView = view;
    viewActive.hidden = view !== "active";
    viewHistory.hidden = view !== "history";
    document.querySelectorAll(".alert-tab").forEach((btn) => {
      const on = btn.dataset.view === view;
      btn.classList.toggle("active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
  }

  async function loadActive() {
    const { ok, body, status } = await api("/api/v1/alerts");
    if (!ok) {
      errorEl.textContent = status === 401 ? "Session expired." : "Could not load alerts.";
      return;
    }
    errorEl.textContent = "";

    if (!body.alerts.length) {
      list.innerHTML = "";
      empty.hidden = false;
      return;
    }

    empty.hidden = true;
    list.innerHTML = body.alerts
      .map(
        (a) => `
      <li class="alert-item" data-testid="alert-item-${a.id}" data-drone-id="${a.drone_id}" data-alert-id="${a.id}">
        <div>
          <strong>${a.message}</strong>
          <div class="hint" style="margin:0.25rem 0 0">${a.drone_id}</div>
        </div>
        <div class="alert-actions">
          ${typeBadge(a.type)}
          <button
            type="button"
            class="btn btn-ack"
            data-testid="ack-${a.id}"
            data-alert-id="${a.id}"
          >Acknowledge</button>
        </div>
      </li>`
      )
      .join("");

    list.querySelectorAll("button.btn-ack").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const alertId = btn.getAttribute("data-alert-id");
        btn.disabled = true;
        const { ok: ackOk, body: ackBody } = await api(`/api/v1/alerts/${alertId}/acknowledge`, {
          method: "POST",
        });
        if (!ackOk) {
          errorEl.textContent = ackBody?.message || "Could not acknowledge alert.";
          btn.disabled = false;
          return;
        }
        await refresh();
      });
    });
  }

  async function loadHistory() {
    const { ok, body, status } = await api("/api/v1/alerts/history");
    if (!ok) {
      errorEl.textContent = status === 401 ? "Session expired." : "Could not load history.";
      return;
    }
    errorEl.textContent = "";

    if (!body.history.length) {
      historyList.innerHTML = "";
      historyEmpty.hidden = false;
      return;
    }

    historyEmpty.hidden = true;
    historyList.innerHTML = body.history
      .map(
        (h) => `
      <li class="alert-item history-item" data-testid="history-item-${h.id}" data-alert-id="${h.id}">
        <div>
          <strong>${h.message}</strong>
          <div class="hint" style="margin:0.25rem 0 0">
            ${h.drone_id} · acknowledged ${formatAgo(h.acknowledged_at)}
          </div>
        </div>
        <div class="alert-actions">
          ${typeBadge(h.type)}
          <span class="badge muted" data-testid="history-acked-label">acked</span>
        </div>
      </li>`
      )
      .join("");
  }

  async function refresh() {
    await updateAlertsNavBadge();
    if (currentView === "active") {
      await loadActive();
    } else {
      await loadHistory();
    }
  }

  document.querySelectorAll(".alert-tab").forEach((btn) => {
    btn.addEventListener("click", async () => {
      setView(btn.dataset.view);
      if (currentView === "active") {
        await loadActive();
      } else {
        await loadHistory();
      }
    });
  });

  await updateAlertsNavBadge();
  await loadActive();
});
