document.addEventListener("DOMContentLoaded", async () => {
  if (!requireAuth()) return;

  const user = getUser();
  const nameEl = document.getElementById("pilot-name");
  if (nameEl && user) nameEl.textContent = user.name || user.email;

  document.getElementById("logout-btn").addEventListener("click", logout);

  const errorEl = document.getElementById("page-error");

  const { ok, body, status } = await api("/api/v1/me");
  if (!ok) {
    errorEl.textContent =
      status === 401 ? "Session expired. Please log in again." : "Could not load profile.";
    if (status === 401) {
      clearSession();
      setTimeout(() => (window.location.href = "/login"), 800);
    }
    return;
  }

  document.getElementById("profile-name").textContent = body.name;
  document.getElementById("profile-role").textContent = `${body.role} · ${body.home_base}`;
  document.getElementById("profile-email").textContent = body.email;
  document.getElementById("profile-pilot-id").textContent = body.pilot_id;
  document.getElementById("profile-license").textContent = body.license_id;
  document.getElementById("profile-home").textContent = body.home_base;
  document.getElementById("profile-last-login").textContent = body.last_login
    ? formatAgo(body.last_login)
    : "—";
  document.getElementById("profile-alerts").textContent = String(body.active_alerts ?? 0);

  const fleet = body.fleet || {};
  document.getElementById("fleet-total").textContent = String(fleet.total ?? 0);
  document.getElementById("fleet-flying").textContent = String(fleet.flying ?? 0);
  document.getElementById("fleet-idle").textContent = String(fleet.idle ?? 0);
  document.getElementById("fleet-offline").textContent = String(fleet.offline ?? 0);

  await updateAlertsNavBadge();
});
