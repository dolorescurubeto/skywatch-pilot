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
  let cachedDrones = [];
  let fitOnNextRender = true;
  let geofenceLayer = null;

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

  function pathColor(drone) {
    if (drone.has_alert) return "#c45c26";
    if (drone.status === "flying") return "#0e7c6b";
    return "#5a7a8a";
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

  function drawFlightPath(drone) {
    const path = drone.flight_path || [];
    const coords = path
      .filter((p) => p.lat != null && p.lon != null)
      .map((p) => [p.lat, p.lon]);
    if (coords.length < 2) return;

    const isFlying = drone.status === "flying";
    const polyline = L.polyline(coords, {
      color: pathColor(drone),
      weight: isFlying ? 6 : 3,
      opacity: isFlying ? 0.95 : 0.55,
      dashArray: isFlying ? null : "6 8",
      className: `flight-path flight-path-${drone.id}`,
    });
    polyline.bindTooltip(`${drone.name} flight path`, { sticky: true });
    polyline.addTo(layer);

    const hit = L.polyline(coords, {
      color: pathColor(drone),
      weight: 12,
      opacity: 0,
      interactive: true,
    });
    hit.bindPopup(
      `<strong>${drone.name}</strong><br/>Flight path (${coords.length} points)<br/>
       <a href="/drones/${drone.id}">Open detail →</a>`
    );
    hit.addTo(layer);
  }

  async function loadGeofence() {
    const { ok, body } = await api("/api/v1/geofence");
    if (!ok || !body?.polygon?.length) return;

    if (geofenceLayer) {
      map.removeLayer(geofenceLayer);
    }

    geofenceLayer = L.polygon(body.polygon, {
      color: "#a33b3b",
      weight: 2,
      dashArray: "8 6",
      fillColor: "#a33b3b",
      fillOpacity: 0.12,
      className: "geofence-zone",
    });
    geofenceLayer.bindTooltip(body.name || "Geofence", { sticky: true });
    geofenceLayer.bindPopup(
      `<strong data-testid="geofence-label">${body.name}</strong><br/>Authorized flight zone`
    );
    geofenceLayer.addTo(map);
  }

  function renderMap(drones) {
    const filtered = drones.filter((d) => matchesFleetFilters(d));
    updateFilterCount(filtered.length, drones.length);

    layer.clearLayers();
    const points = [];

    filtered.forEach((d) => {
      if (d.lat == null || d.lon == null) return;
      points.push([d.lat, d.lon]);
      (d.flight_path || []).forEach((p) => {
        if (p.lat != null && p.lon != null) points.push([p.lat, p.lon]);
      });

      drawFlightPath(d);

      const marker = L.marker([d.lat, d.lon], { icon: makeIcon(d) });
      const batt = batteryText(d.battery_percent);
      const pathLen = (d.flight_path || []).length;
      const geoNote = (d.alerts || []).some((a) => a.type === "GEOFENCE_BREACH")
        ? "<br/><em>Outside geofence</em>"
        : "";
      marker.bindPopup(
        `<strong>${d.name}</strong><br/>${d.status} · ${batt}<br/>
         Path points: ${pathLen}${geoNote}<br/>
         <a href="/drones/${d.id}">Open detail →</a>`
      );
      marker.addTo(layer);
    });

    if (fitOnNextRender && points.length) {
      map.fitBounds(points, { padding: [40, 40], maxZoom: 14 });
      fitOnNextRender = false;
    }
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
    cachedDrones = body.drones || [];
    renderMap(cachedDrones);

    if (refreshedEl) {
      refreshedEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
    }
    await updateAlertsNavBadge();
  }

  function onFilterChange() {
    fitOnNextRender = true;
    renderMap(cachedDrones);
  }

  document.getElementById("filter-status").addEventListener("change", onFilterChange);
  document.getElementById("filter-alerts").addEventListener("change", onFilterChange);

  await loadGeofence();
  await loadMap();
  setTimeout(() => map.invalidateSize(), 100);
  setInterval(loadMap, REFRESH_MS);
});
