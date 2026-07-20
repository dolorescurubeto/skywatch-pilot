const REFRESH_MS = 15000;

document.addEventListener("DOMContentLoaded", async () => {
  if (!requireAuth()) return;

  const user = getUser();
  const nameEl = document.getElementById("pilot-name");
  if (nameEl && user) nameEl.textContent = user.name || user.email;

  document.getElementById("logout-btn").addEventListener("click", logout);

  const tbody = document.getElementById("drones-body");
  const errorEl = document.getElementById("page-error");
  const refreshedEl = document.getElementById("last-refreshed");

  async function loadDrones() {
    const { ok, body, status } = await api("/api/v1/drones");
    if (!ok) {
      errorEl.textContent =
        status === 401 ? "Session expired. Please log in again." : "Could not load drones.";
      if (status === 401) {
        clearSession();
        setTimeout(() => (window.location.href = "/login"), 800);
      }
      return;
    }

    errorEl.textContent = "";
    tbody.innerHTML = body.drones
      .map((d) => {
        const alertBadge = d.has_alert
          ? `<span class="badge warn" data-testid="alert-badge-${d.id}">alert</span>`
          : `<span class="badge muted">—</span>`;
        return `
      <tr class="clickable" data-testid="drone-row-${d.id}" data-id="${d.id}">
        <td><strong>${d.name}</strong></td>
        <td>${statusBadge(d.status)}</td>
        <td>${batteryText(d.battery_percent)}</td>
        <td>${formatAgo(d.last_seen)}</td>
        <td>${alertBadge}</td>
      </tr>`;
      })
      .join("");

    tbody.querySelectorAll("tr.clickable").forEach((row) => {
      row.addEventListener("click", () => {
        window.location.href = `/drones/${row.dataset.id}`;
      });
    });

    if (refreshedEl) {
      const now = new Date();
      refreshedEl.textContent = `Updated ${now.toLocaleTimeString()}`;
    }

    await updateAlertsNavBadge();
  }

  await loadDrones();
  setInterval(loadDrones, REFRESH_MS);
});
