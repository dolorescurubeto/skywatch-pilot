const REFRESH_MS = 15000;

document.addEventListener("DOMContentLoaded", async () => {
  if (!requireAuth()) return;

  const user = getUser();
  const nameEl = document.getElementById("pilot-name");
  if (nameEl && user) nameEl.textContent = user.name || user.email;

  document.getElementById("logout-btn").addEventListener("click", logout);

  const errorEl = document.getElementById("page-error");
  const refreshedEl = document.getElementById("last-refreshed");
  const mapEl = document.getElementById("fleet-map");

  // Default center: Buenos Aires (seed coords)
  const map = L.map(mapEl).setView([-34.605, -58.385], 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);

  const layer = L.layerGroup().addTo(map);

  function markerColor(drone) {
    if (drone.has_alert) return "#c45c26";
    if (drone.status === "flying") return "#0e7c6b";
    if (drone.status === "offline") return "#a33b3b";
    return "#3a4f5c";
  }

  function makeIcon(drone) {
    const color = markerColor(drone);
    return L.divIcon({
      className: "drone-marker",
      html: `<div style="
        width:16px;height:16px;border-radius:50%;
        background:${color};border:2px solid #fff;
        box-shadow:0 2px 8px rgba(0,0,0,0.35);
      " data-testid="marker-${drone.id}"></div>`,
      iconSize: [16, 16],
      iconAnchor: [8, 8],
    });
  }

  async function loadMap() {
    const { ok, body, status } = await api("/api/v1/drones");
    if (!ok) {
      errorEl.textContent =
        status === 401 ? "Session expired. Please log in again." : "Could not load map.";
      if (status === 401) {
        clearSession();
        setTimeout(() => (window.location.href = "/login"), 800);
      }
      return;
    }

    errorEl.textContent = "";
    layer.clearLayers();

    const points = [];
    body.drones.forEach((d) => {
      if (d.lat == null || d.lon == null) return;
      points.push([d.lat, d.lon]);
      const marker = L.marker([d.lat, d.lon], { icon: makeIcon(d) });
      const batt = batteryText(d.battery_percent);
      marker.bindPopup(
        `<strong>${d.name}</strong><br/>${d.status} · ${batt}<br/>
         <a href="/drones/${d.id}">Open detail →</a>`
      );
      marker.on("click", () => {
        // double-click path to detail via popup link; single click opens popup
      });
      marker.addTo(layer);
    });

    if (points.length) {
      map.fitBounds(points, { padding: [40, 40], maxZoom: 14 });
    }

    if (refreshedEl) {
      refreshedEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
    }
    await updateAlertsNavBadge();
  }

  await loadMap();
  // Leaflet needs a resize after panel layout
  setTimeout(() => map.invalidateSize(), 100);
  setInterval(loadMap, REFRESH_MS);
});
