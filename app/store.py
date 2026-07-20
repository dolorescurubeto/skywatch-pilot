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
    """Short history for detail screen (5 readings)."""
    now = utc_now()
    readings = []
    battery = drone.get("battery_percent")
    for i in range(5, 0, -1):
        ts = now - timedelta(minutes=i)
        b = battery
        if b is not None:
            b = max(0, min(100, b + (5 - i)))
        readings.append(
            {
                "ts": to_iso(ts),
                "battery_percent": b,
                "status": drone["status"] if i == 1 else "idle",
                "altitude_m": drone.get("altitude_m"),
                "lat": drone.get("lat"),
                "lon": drone.get("lon"),
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


def load_acknowledgements() -> dict[str, list[str]]:
    acks = _acks_file()
    if not acks.exists():
        return {}
    with open(acks, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def save_acknowledgements(data: dict[str, list[str]]) -> None:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(_acks_file(), encoding="utf-8", mode="w") as f:
        json.dump(data, f, indent=2)


def clear_all_acknowledgements() -> None:
    save_acknowledgements({})


def get_acknowledged_ids(pilot_id: str) -> set[str]:
    data = load_acknowledgements()
    return set(data.get(pilot_id, []))


def acknowledge_alert(pilot_id: str, alert_id: str) -> None:
    data = load_acknowledgements()
    ids = list(data.get(pilot_id, []))
    if alert_id not in ids:
        ids.append(alert_id)
    data[pilot_id] = ids
    save_acknowledgements(data)


def prune_acknowledgements(pilot_id: str, active_alert_ids: set[str]) -> None:
    """Drop acks for alerts that are no longer active (condition cleared)."""
    data = load_acknowledgements()
    current = set(data.get(pilot_id, []))
    kept = sorted(current & active_alert_ids)
    if set(data.get(pilot_id, [])) != set(kept):
        data[pilot_id] = kept
        save_acknowledgements(data)


def drones_for_pilot(pilot_id: str) -> list[dict]:
    return [deepcopy(d) for d in load_drones() if d["pilot_id"] == pilot_id]


def get_drone(drone_id: str) -> dict | None:
    for d in load_drones():
        if d["id"] == drone_id:
            return deepcopy(d)
    return None
