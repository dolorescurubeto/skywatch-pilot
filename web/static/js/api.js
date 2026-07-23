const TOKEN_KEY = "skywatch_token";
const USER_KEY = "skywatch_user";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function getUser() {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

function setSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = "/login";
    return false;
  }
  return true;
}

async function api(path, options = {}) {
  const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(path, { ...options, headers });
  let body = null;
  try {
    body = await res.json();
  } catch (_) {
    body = null;
  }
  return { ok: res.ok, status: res.status, body };
}

function statusBadge(status) {
  if (status === "flying") return `<span class="badge ok">${status}</span>`;
  if (status === "offline") return `<span class="badge danger">${status}</span>`;
  return `<span class="badge muted">${status}</span>`;
}

function formatAgo(iso) {
  if (!iso) return "—";
  const then = new Date(iso);
  const mins = Math.max(0, Math.round((Date.now() - then.getTime()) / 60000));
  if (mins < 1) return "just now";
  if (mins === 1) return "1 min ago";
  return `${mins} min ago`;
}

function batteryText(value) {
  return value === null || value === undefined ? "—" : `${value}%`;
}

/** Client-side fleet filters (status + has_alert + name search). */
function readFleetFilters() {
  const statusEl = document.getElementById("filter-status");
  const alertsEl = document.getElementById("filter-alerts");
  const searchEl = document.getElementById("filter-search");
  return {
    status: statusEl ? statusEl.value : "all",
    alerts: alertsEl ? alertsEl.value : "all",
    search: searchEl ? searchEl.value.trim().toLowerCase() : "",
  };
}

function matchesFleetFilters(drone, filters = readFleetFilters()) {
  if (filters.status !== "all" && drone.status !== filters.status) return false;
  if (filters.alerts === "alert" && !drone.has_alert) return false;
  if (filters.search) {
    const name = (drone.name || "").toLowerCase();
    const id = (drone.id || "").toLowerCase();
    if (!name.includes(filters.search) && !id.includes(filters.search)) return false;
  }
  return true;
}

function updateFilterCount(shown, total) {
  const el = document.getElementById("filter-count");
  if (!el) return;
  el.textContent = `Showing ${shown} of ${total}`;
}

const SEEN_ALERTS_KEY = "skywatch_seen_alert_ids";

function getSeenAlertIds() {
  try {
    return new Set(JSON.parse(sessionStorage.getItem(SEEN_ALERTS_KEY) || "[]"));
  } catch (_) {
    return new Set();
  }
}

function setSeenAlertIds(ids) {
  sessionStorage.setItem(SEEN_ALERTS_KEY, JSON.stringify([...ids]));
}

/** Floating toast for new alerts (demo / UX). */
function showToast(message, opts = {}) {
  let host = document.getElementById("toast-host");
  if (!host) {
    host = document.createElement("div");
    host.id = "toast-host";
    host.className = "toast-host";
    host.setAttribute("data-testid", "toast-host");
    document.body.appendChild(host);
  }
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.setAttribute("data-testid", "alert-toast");
  toast.setAttribute("role", "status");
  toast.textContent = message;
  host.appendChild(toast);
  const ms = opts.durationMs || 4500;
  setTimeout(() => {
    toast.classList.add("toast-out");
    setTimeout(() => toast.remove(), 280);
  }, ms);
}

function notifyNewAlerts(alerts) {
  const ids = (alerts || []).map((a) => a.id);
  const seen = getSeenAlertIds();
  if (seen.size === 0) {
    // First load: remember current alerts, do not toast
    setSeenAlertIds(ids);
    return;
  }
  const newcomers = (alerts || []).filter((a) => !seen.has(a.id));
  if (newcomers.length) {
    const first = newcomers[0];
    const extra = newcomers.length > 1 ? ` (+${newcomers.length - 1} more)` : "";
    showToast(`New alert: ${first.message}${extra}`);
  }
  setSeenAlertIds(ids);
}

async function logout() {
  const token = getToken();
  if (token) {
    try {
      await api("/api/v1/auth/logout", { method: "POST" });
    } catch (_) {
      /* ignore */
    }
  }
  clearSession();
  sessionStorage.removeItem(SEEN_ALERTS_KEY);
  window.location.href = "/login";
}

/** Updates "Alerts (N)" badge in the top nav + toast on new alerts. */
async function updateAlertsNavBadge() {
  const el = document.querySelector("[data-testid='nav-alerts']");
  if (!el || !getToken()) return;

  const { ok, body } = await api("/api/v1/alerts");
  if (!ok) return;

  const alerts = body.alerts || [];
  notifyNewAlerts(alerts);

  const count = body.count || 0;
  const label = count > 0 ? `Alerts (${count})` : "Alerts";
  el.innerHTML =
    count > 0
      ? `${label} <span class="nav-count" data-testid="alerts-nav-badge">${count}</span>`
      : label;
}
