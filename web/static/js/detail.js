document.addEventListener("DOMContentLoaded", async () => {
  if (!requireAuth()) return;
  document.getElementById("logout-btn").addEventListener("click", logout);

  const user = getUser();
  const nameEl = document.getElementById("pilot-name");
  if (nameEl && user) nameEl.textContent = user.name || user.email;

  await updateAlertsNavBadge();

  const parts = window.location.pathname.split("/").filter(Boolean);
  const droneId = parts[parts.length - 1];
  const errorEl = document.getElementById("page-error");

  function renderDetail(body) {
    document.getElementById("drone-name").textContent = body.name;
    document.getElementById("drone-id").textContent = `ID: ${body.id}`;

    document.getElementById("meta-grid").innerHTML = `
      <div class="meta"><span>Status</span><strong data-testid="detail-status">${body.status}</strong></div>
      <div class="meta"><span>Battery</span><strong>${batteryText(body.battery_percent)}</strong></div>
      <div class="meta"><span>Altitude</span><strong>${body.altitude_m ?? "—"} m</strong></div>
      <div class="meta"><span>Lat</span><strong>${body.lat ?? "—"}</strong></div>
      <div class="meta"><span>Lon</span><strong>${body.lon ?? "—"}</strong></div>
      <div class="meta"><span>Last seen</span><strong>${formatAgo(body.last_seen)}</strong></div>
    `;

    const history = body.history || [];
    document.getElementById("history-body").innerHTML = history.length
      ? history
          .slice()
          .reverse()
          .map(
            (h) => `
      <tr>
        <td>${formatAgo(h.ts)}</td>
        <td>${statusBadge(h.status)}</td>
        <td>${batteryText(h.battery_percent)}</td>
        <td>${h.altitude_m ?? "—"}</td>
      </tr>`
          )
          .join("")
      : `<tr><td colspan="4">No history yet.</td></tr>`;

    document.querySelectorAll(".btn-status").forEach((btn) => {
      const target = btn.getAttribute("data-status");
      btn.disabled = body.status === target;
      btn.classList.toggle("active-status", body.status === target);
    });
  }

  async function loadDetail() {
    const { ok, body, status } = await api(`/api/v1/drones/${droneId}`);
    if (!ok) {
      errorEl.textContent =
        status === 403
          ? "Not your drone."
          : status === 404
            ? "Drone not found."
            : "Could not load drone.";
      return null;
    }
    errorEl.textContent = "";
    renderDetail(body);
    return body;
  }

  document.querySelectorAll(".btn-status").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const newStatus = btn.getAttribute("data-status");
      btn.disabled = true;
      const { ok, body, status } = await api(`/api/v1/drones/${droneId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      if (!ok) {
        errorEl.textContent = body?.message || "Could not update status.";
        await loadDetail();
        return;
      }
      errorEl.textContent = "";
      showToast(`${body.drone.name} is now ${body.drone.status}`);
      renderDetail(body.drone);
      await updateAlertsNavBadge();
    });
  });

  await loadDetail();
});
