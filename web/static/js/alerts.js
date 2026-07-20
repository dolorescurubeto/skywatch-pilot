document.addEventListener("DOMContentLoaded", async () => {
  if (!requireAuth()) return;
  document.getElementById("logout-btn").addEventListener("click", logout);

  const list = document.getElementById("alerts-list");
  const empty = document.getElementById("alerts-empty");
  const errorEl = document.getElementById("page-error");

  async function loadAlerts() {
    await updateAlertsNavBadge();

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
      .map((a) => {
        const badge =
          a.type === "OFFLINE"
            ? `<span class="badge danger">${a.type}</span>`
            : `<span class="badge warn">${a.type}</span>`;
        return `
      <li class="alert-item" data-testid="alert-${a.drone_id}" data-alert-id="${a.id}">
        <div>
          <strong>${a.message}</strong>
          <div class="hint" style="margin:0.25rem 0 0">${a.drone_id}</div>
        </div>
        <div class="alert-actions">
          ${badge}
          <button
            type="button"
            class="btn btn-ack"
            data-testid="ack-${a.id}"
            data-alert-id="${a.id}"
          >Acknowledge</button>
        </div>
      </li>`;
      })
      .join("");

    list.querySelectorAll("button.btn-ack").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const alertId = btn.getAttribute("data-alert-id");
        btn.disabled = true;
        const { ok: ackOk, body: ackBody } = await api(
          `/api/v1/alerts/${alertId}/acknowledge`,
          { method: "POST" }
        );
        if (!ackOk) {
          errorEl.textContent = ackBody?.message || "Could not acknowledge alert.";
          btn.disabled = false;
          return;
        }
        await loadAlerts();
      });
    });
  }

  await loadAlerts();
});
