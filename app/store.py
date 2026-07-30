"""Load and persist SkyWatch data (SQLAlchemy / SQLite or Postgres)."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select

from app.db import get_engine, init_db, reset_engine, session_scope
from app.models import AckActive, AckHistory, Drone, User

OFFLINE_AFTER_SECONDS = 5 * 60  # 5 minutes
ALLOWED_MANUAL_STATUSES = frozenset({"idle", "flying"})


def get_data_dir() -> Path:
    """Seed JSON files still live here (bootstrap only)."""
    override = os.environ.get("SKYWATCH_DATA_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "data"


def _users_seed_file() -> Path:
    return get_data_dir() / "users.json"


def _drones_seed_file() -> Path:
    return get_data_dir() / "drones_seed.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _user_to_dict(u: User) -> dict:
    return {
        "email": u.email,
        "password": u.password,
        "pilot_id": u.pilot_id,
        "token": u.token,
        "name": u.name,
        "role": u.role or "Pilot",
        "home_base": u.home_base or "",
        "license_id": u.license_id or "",
        "last_login": u.last_login,
    }


def _drone_to_dict(d: Drone) -> dict:
    try:
        history = json.loads(d.history_json or "[]")
    except json.JSONDecodeError:
        history = []
    return {
        "id": d.id,
        "pilot_id": d.pilot_id,
        "name": d.name,
        "status": d.status,
        "battery_percent": d.battery_percent,
        "altitude_m": d.altitude_m,
        "lat": d.lat,
        "lon": d.lon,
        "last_seen": d.last_seen,
        "history": history,
    }


def _apply_drone_dict(row: Drone, data: dict) -> None:
    row.pilot_id = data["pilot_id"]
    row.name = data["name"]
    row.status = data["status"]
    row.battery_percent = data.get("battery_percent")
    row.altitude_m = data.get("altitude_m")
    row.lat = data.get("lat")
    row.lon = data.get("lon")
    row.last_seen = data.get("last_seen")
    row.history_json = json.dumps(data.get("history") or [])


def ensure_db() -> None:
    init_db()


def seed_users_from_json_if_empty() -> None:
    """Bootstrap demo users from data/users.json when DB has no users."""
    ensure_db()
    with session_scope() as session:
        count = session.scalar(select(User.id).limit(1))
        if count is not None:
            return
        path = _users_seed_file()
        if not path.exists():
            return
        users = json.loads(path.read_text(encoding="utf-8"))
        for u in users:
            session.add(
                User(
                    email=u["email"],
                    password=u["password"],
                    pilot_id=u["pilot_id"],
                    token=u["token"],
                    name=u.get("name") or u["email"],
                    role=u.get("role") or "Pilot",
                    home_base=u.get("home_base") or "",
                    license_id=u.get("license_id") or "",
                    last_login=u.get("last_login"),
                )
            )


def load_users() -> list[dict]:
    ensure_db()
    with session_scope() as session:
        rows = session.scalars(select(User).order_by(User.id)).all()
        return [_user_to_dict(u) for u in rows]


def find_user_by_email(email: str) -> dict | None:
    ensure_db()
    email_l = email.strip().lower()
    with session_scope() as session:
        row = session.scalar(select(User).where(User.email == email_l))
        # emails in seed are mixed case — compare case-insensitive
        if row is None:
            rows = session.scalars(select(User)).all()
            for u in rows:
                if u.email.lower() == email_l:
                    return _user_to_dict(u)
            return None
        return _user_to_dict(row)


def find_user_by_token(token: str) -> dict | None:
    ensure_db()
    with session_scope() as session:
        row = session.scalar(select(User).where(User.token == token))
        return _user_to_dict(row) if row else None


def record_login(email: str) -> dict | None:
    ensure_db()
    email_l = email.strip().lower()
    with session_scope() as session:
        rows = session.scalars(select(User)).all()
        for u in rows:
            if u.email.lower() == email_l:
                u.last_login = to_iso(utc_now())
                session.flush()
                return _user_to_dict(u)
    return None


def public_profile(user: dict) -> dict:
    return {
        "pilot_id": user["pilot_id"],
        "name": user.get("name") or user["email"],
        "email": user["email"],
        "role": user.get("role") or "Pilot",
        "home_base": user.get("home_base") or "—",
        "license_id": user.get("license_id") or "—",
        "last_login": user.get("last_login"),
    }


def _initial_history(drone: dict) -> list[dict]:
    now = utc_now()
    readings = []
    battery = drone.get("battery_percent")
    base_lat = drone.get("lat") or -34.60
    base_lon = drone.get("lon") or -58.38
    for i in range(8, 0, -1):
        ts = now - timedelta(minutes=i)
        b = battery
        if b is not None:
            b = max(0, min(100, b + (8 - i)))
        step = 8 - i
        if drone.get("status") == "flying":
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


def _seed_drones() -> list[dict]:
    with open(_drones_seed_file(), encoding="utf-8") as f:
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


def load_drones() -> list[dict]:
    ensure_db()
    with session_scope() as session:
        rows = session.scalars(select(Drone)).all()
        if not rows:
            return []
        return [_drone_to_dict(d) for d in rows]


def save_drones(drones: list[dict]) -> None:
    ensure_db()
    with session_scope() as session:
        existing = {d.id: d for d in session.scalars(select(Drone)).all()}
        seen = set()
        for data in drones:
            seen.add(data["id"])
            row = existing.get(data["id"])
            if row is None:
                row = Drone(id=data["id"])
                session.add(row)
            _apply_drone_dict(row, data)
        for drone_id, row in existing.items():
            if drone_id not in seen:
                session.delete(row)


def drones_count() -> int:
    ensure_db()
    with session_scope() as session:
        return len(session.scalars(select(Drone.id)).all())


def reset_drones_from_seed() -> list[dict]:
    drones = _seed_drones()
    save_drones(drones)
    clear_all_acknowledgements()
    return drones


def clear_all_acknowledgements() -> None:
    ensure_db()
    with session_scope() as session:
        session.execute(delete(AckActive))
        session.execute(delete(AckHistory))


def get_acknowledged_ids(pilot_id: str) -> set[str]:
    ensure_db()
    with session_scope() as session:
        rows = session.scalars(select(AckActive.alert_id).where(AckActive.pilot_id == pilot_id)).all()
        return set(rows)


def get_alert_history(pilot_id: str) -> list[dict]:
    ensure_db()
    with session_scope() as session:
        rows = session.scalars(
            select(AckHistory)
            .where(AckHistory.pilot_id == pilot_id)
            .order_by(AckHistory.id.desc())
        ).all()
        return [
            {
                "id": r.alert_id,
                "drone_id": r.drone_id,
                "drone_name": r.drone_name,
                "type": r.type,
                "message": r.message,
                "battery_percent": r.battery_percent,
                "acknowledged_at": r.acknowledged_at,
            }
            for r in rows
        ]


def acknowledge_alert(pilot_id: str, alert: dict) -> None:
    ensure_db()
    alert_id = alert["id"]
    with session_scope() as session:
        exists = session.scalar(
            select(AckActive).where(AckActive.pilot_id == pilot_id, AckActive.alert_id == alert_id)
        )
        if exists is None:
            session.add(AckActive(pilot_id=pilot_id, alert_id=alert_id))
        session.add(
            AckHistory(
                pilot_id=pilot_id,
                alert_id=alert_id,
                drone_id=alert.get("drone_id"),
                drone_name=alert.get("drone_name"),
                type=alert.get("type"),
                message=alert.get("message"),
                battery_percent=alert.get("battery_percent"),
                acknowledged_at=to_iso(utc_now()),
            )
        )
        # Keep last 50 history rows per pilot
        ids = session.scalars(
            select(AckHistory.id)
            .where(AckHistory.pilot_id == pilot_id)
            .order_by(AckHistory.id.desc())
        ).all()
        if len(ids) > 50:
            for old_id in ids[50:]:
                session.execute(delete(AckHistory).where(AckHistory.id == old_id))


def prune_acknowledgements(pilot_id: str, active_alert_ids: set[str]) -> None:
    ensure_db()
    with session_scope() as session:
        rows = session.scalars(select(AckActive).where(AckActive.pilot_id == pilot_id)).all()
        for row in rows:
            if row.alert_id not in active_alert_ids:
                session.delete(row)


def drones_for_pilot(pilot_id: str) -> list[dict]:
    return [deepcopy(d) for d in load_drones() if d["pilot_id"] == pilot_id]


def get_drone(drone_id: str) -> dict | None:
    ensure_db()
    with session_scope() as session:
        row = session.get(Drone, drone_id)
        return _drone_to_dict(row) if row else None


def update_drone_status(drone_id: str, pilot_id: str, new_status: str) -> dict | None:
    if new_status not in ALLOWED_MANUAL_STATUSES:
        raise ValueError("status must be idle or flying")

    drones = load_drones()
    for d in drones:
        if d["id"] != drone_id:
            continue
        if d["pilot_id"] != pilot_id:
            return None

        now = utc_now()
        d["status"] = new_status
        d["last_seen"] = to_iso(now)

        if new_status == "flying":
            if not d.get("altitude_m") or d.get("altitude_m") == 0:
                d["altitude_m"] = 40.0
            if d.get("battery_percent") is None:
                d["battery_percent"] = 50
        else:
            d["altitude_m"] = 0.0

        history = d.get("history") or []
        history.append(
            {
                "ts": to_iso(now),
                "battery_percent": d.get("battery_percent"),
                "status": new_status,
                "altitude_m": d.get("altitude_m"),
                "lat": d.get("lat"),
                "lon": d.get("lon"),
            }
        )
        d["history"] = history[-10:]
        save_drones(drones)
        return deepcopy(d)

    return None


def bootstrap_database(*, force_reset_drones: bool = False, reset_eng: bool = False) -> None:
    """
    Init schema, seed users if empty, seed drones if empty or force_reset.
    """
    if reset_eng:
        reset_engine()
    ensure_db()
    seed_users_from_json_if_empty()
    if force_reset_drones or drones_count() == 0:
        reset_drones_from_seed()
