"""Load and persist SkyWatch data (JSON files)."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path


def get_data_dir() -> Path:
    override = os.environ.get("SKYWATCH_DATA_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "data"


def _users_file() -> Path:
    return get_data_dir() / "users.json"


def _drones_seed() -> Path:
    return get_data_dir() / "drones_seed.json"


def _drones_state() -> Path:
    return get_data_dir() / "drones_state.json"


def _acks_file() -> Path:
    return get_data_dir() / "acknowledged_alerts.json"


OFFLINE_AFTER_SECONDS = 5 * 60  # 5 minutes


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def load_users() -> list[dict]:
    with open(_users_file(), encoding="utf-8") as f:
        return json.load(f)


def save_users(users: list[dict]) -> None:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(_users_file(), encoding="utf-8", mode="w") as f:
        json.dump(users, f, indent=2)


def find_user_by_email(email: str) -> dict | None:
    email_l = email.strip().lower()
    for user in load_users():
        if user["email"].lower() == email_l:
            return user
    return None


def find_user_by_token(token: str) -> dict | None:
    for user in load_users():
        if user["token"] == token:
            return user
    return None


def record_login(email: str) -> dict | None:
    """Update last_login for the user and return the refreshed user dict."""
    users = load_users()
    email_l = email.strip().lower()
    for user in users:
        if user["email"].lower() == email_l:
            user["last_login"] = to_iso(utc_now())
            save_users(users)
            return deepcopy(user)
    return None


def public_profile(user: dict) -> dict:
    """Safe fields for profile API (no password/token)."""
    return {
        "pilot_id": user["pilot_id"],
        "name": user.get("name") or user["email"],
        "email": user["email"],
        "role": user.get("role") or "Pilot",
        "home_base": user.get("home_base") or "—",
        "license_id": user.get("license_id") or "—",
        "last_login": user.get("last_login"),
    }


def _seed_drones() -> list[dict]:
    with open(_drones_seed(), encoding="utf-8") as f:
        drones = json.load(f)
    now = utc_now()
    for d in drones:
        if d["status"] == "offline":
            d["last_seen"] = to_iso(now - timedelta(minutes=12))
            d["battery_percent"] = None
        elif d["id"] == "drn_02":
            d["last_seen"] = to_iso(now - timedelta(minutes=2))
        else:
            d["last_seen"] = to_iso(now)
        d["history"] = _initial_history(d)
    return drones


def _initial_history(drone: dict) -> list[dict]:
    """History for detail screen + a clearly visible map flight path."""
    now = utc_now()
    readings = []
    battery = drone.get("battery_percent")
    base_lat = drone.get("lat") or -34.60
    base_lon = drone.get("lon") or -58.38
    # ~1.5–2 km trail so paths read clearly at city zoom (not hidden under the marker)
    for i in range(8, 0, -1):
        ts = now - timedelta(minutes=i)
        b = battery
        if b is not None:
            b = max(0, min(100, b + (8 - i)))
        step = 8 - i  # 0..7 along the route toward current position
        if drone.get("status") == "flying":
            # Diagonal approach into current lat/lon
            lat = round(base_lat - 0.0028 * (7 - step), 5)
            lon = round(base_lon - 0.0035 * (7 - step), 5)
            status = "flying"
            alt = drone.get("altitude_m") or 40.0
        else:
            lat = base_lat
            lon = base_lon
            status = drone["status"] if i == 1 else "idle"
            alt = drone.get("altitude_m")
        readings.append(
            {
                "ts": to_iso(ts),
                "battery_percent": b,
                "status": status,
                "altitude_m": alt,
                "lat": lat,
                "lon": lon,
            }
        )
    return readings


def load_drones() -> list[dict]:
    state = _drones_state()
    if not state.exists():
        drones = _seed_drones()
        save_drones(drones)
        return drones
    with open(state, encoding="utf-8") as f:
        return json.load(f)


def save_drones(drones: list[dict]) -> None:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(_drones_state(), encoding="utf-8", mode="w") as f:
        json.dump(drones, f, indent=2)


def reset_drones_from_seed() -> list[dict]:
    drones = _seed_drones()
    save_drones(drones)
    clear_all_acknowledgements()
    return drones


def load_acknowledgements() -> dict:
    """
    Per-pilot ack store:
      { pilot_id: { "active": [alert_id, ...], "history": [ {alert snapshot + acknowledged_at}, ... ] } }

    Migrates legacy format { pilot_id: [alert_id, ...] }.
    """
    acks = _acks_file()
    if not acks.exists():
        return {}
    with open(acks, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}

    migrated: dict = {}
    for pilot_id, value in data.items():
        if isinstance(value, list):
            # Legacy: list of ids only
            migrated[pilot_id] = {"active": list(value), "history": []}
        elif isinstance(value, dict):
            migrated[pilot_id] = {
                "active": list(value.get("active") or []),
                "history": list(value.get("history") or []),
            }
        else:
            migrated[pilot_id] = {"active": [], "history": []}
    return migrated


def save_acknowledgements(data: dict) -> None:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(_acks_file(), encoding="utf-8", mode="w") as f:
        json.dump(data, f, indent=2)


def clear_all_acknowledgements() -> None:
    save_acknowledgements({})


def get_acknowledged_ids(pilot_id: str) -> set[str]:
    data = load_acknowledgements()
    entry = data.get(pilot_id) or {}
    return set(entry.get("active") or [])


def get_alert_history(pilot_id: str) -> list[dict]:
    """Acknowledged alerts newest-first (append-only history)."""
    data = load_acknowledgements()
    entry = data.get(pilot_id) or {}
    history = list(entry.get("history") or [])
    history.reverse()
    return history


def acknowledge_alert(pilot_id: str, alert: dict) -> None:
    """Mark alert as acknowledged for active filtering and append to history."""
    data = load_acknowledgements()
    entry = data.get(pilot_id) or {"active": [], "history": []}
    alert_id = alert["id"]
    active = list(entry.get("active") or [])
    if alert_id not in active:
        active.append(alert_id)

    history = list(entry.get("history") or [])
    history.append(
        {
            "id": alert_id,
            "drone_id": alert.get("drone_id"),
            "drone_name": alert.get("drone_name"),
            "type": alert.get("type"),
            "message": alert.get("message"),
            "battery_percent": alert.get("battery_percent"),
            "acknowledged_at": to_iso(utc_now()),
        }
    )
    # Keep last 50 history rows
    history = history[-50:]

    data[pilot_id] = {"active": active, "history": history}
    save_acknowledgements(data)


def prune_acknowledgements(pilot_id: str, active_alert_ids: set[str]) -> None:
    """Drop *active* acks for alerts that are no longer firing (history is kept)."""
    data = load_acknowledgements()
    entry = data.get(pilot_id) or {"active": [], "history": []}
    current = set(entry.get("active") or [])
    kept = sorted(current & active_alert_ids)
    if set(entry.get("active") or []) != set(kept):
        entry["active"] = kept
        entry["history"] = list(entry.get("history") or [])
        data[pilot_id] = entry
        save_acknowledgements(data)


def drones_for_pilot(pilot_id: str) -> list[dict]:
    return [deepcopy(d) for d in load_drones() if d["pilot_id"] == pilot_id]


def get_drone(drone_id: str) -> dict | None:
    for d in load_drones():
        if d["id"] == drone_id:
            return deepcopy(d)
    return None
