"""Alert rules for SkyWatch Pilot v1."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from app.store import (
    OFFLINE_AFTER_SECONDS,
    acknowledge_alert,
    get_acknowledged_ids,
    parse_iso,
    prune_acknowledgements,
    utc_now,
)


def _minutes_since(last_seen: str | None, now: datetime | None = None) -> float | None:
    now = now or utc_now()
    dt = parse_iso(last_seen)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 60.0


def compute_alerts_for_drone(drone: dict, now: datetime | None = None) -> list[dict]:
    """Return rule-based alerts for one drone (ignores acknowledgements)."""
    now = now or utc_now()
    alerts: list[dict] = []
    drone_id = drone["id"]
    name = drone["name"]
    status = drone.get("status")
    battery = drone.get("battery_percent")
    mins = _minutes_since(drone.get("last_seen"), now)

    offline = status == "offline" or (mins is not None and mins * 60 > OFFLINE_AFTER_SECONDS)
    if offline:
        ago = int(mins) if mins is not None else 12
        alerts.append(
            {
                "id": f"alert_{drone_id}_offline",
                "drone_id": drone_id,
                "drone_name": name,
                "type": "OFFLINE",
                "message": f"{name} - Offline ({ago} min)",
                "battery_percent": battery,
            }
        )
        return alerts

    if battery is not None and battery < 20:
        alerts.append(
            {
                "id": f"alert_{drone_id}_battery",
                "drone_id": drone_id,
                "drone_name": name,
                "type": "LOW_BATTERY",
                "message": f"{name} - Low battery ({battery}%)",
                "battery_percent": battery,
            }
        )
    return alerts


def compute_alerts_for_pilot(drones: list[dict], pilot_id: str) -> list[dict]:
    own = [d for d in drones if d["pilot_id"] == pilot_id]
    raw: list[dict] = []
    for d in own:
        raw.extend(compute_alerts_for_drone(d))

    active_ids = {a["id"] for a in raw}
    prune_acknowledgements(pilot_id, active_ids)
    acked = get_acknowledged_ids(pilot_id)
    return [a for a in raw if a["id"] not in acked]


def acknowledge_alert_for_pilot(pilot_id: str, alert_id: str, drones: list[dict]) -> dict | None:
    """
    Acknowledge an alert if it is currently active for this pilot.
    Returns the alert dict, or None if not found / not owned.
    """
    own = [d for d in drones if d["pilot_id"] == pilot_id]
    candidates: list[dict] = []
    for d in own:
        candidates.extend(compute_alerts_for_drone(d))
    match = next((a for a in candidates if a["id"] == alert_id), None)
    if not match:
        return None
    acknowledge_alert(pilot_id, alert_id)
    return match


def enrich_drone_list_item(drone: dict, pilot_id: str | None = None) -> dict:
    """List row: flags if any *unacknowledged* alert."""
    item = deepcopy(drone)
    alerts = compute_alerts_for_drone(drone)
    if pilot_id:
        acked = get_acknowledged_ids(pilot_id)
        alerts = [a for a in alerts if a["id"] not in acked]
    item["has_alert"] = len(alerts) > 0
    item["alerts"] = alerts
    item.pop("history", None)
    return item
