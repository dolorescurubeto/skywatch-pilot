"""Background telemetry simulator — updates drone state every few seconds."""

from __future__ import annotations

import random
import threading
import time
from datetime import timedelta

from app.store import load_drones, save_drones, to_iso, utc_now

_stop = threading.Event()
_thread: threading.Thread | None = None


def tick_once() -> None:
    """One simulation step (also useful in tests)."""
    drones = load_drones()
    now = utc_now()
    for d in drones:
        if d["status"] == "offline":
            # Stay offline; occasionally "come back" (10% chance)
            if random.random() < 0.10:
                d["status"] = "idle"
                d["battery_percent"] = random.randint(25, 60)
                d["altitude_m"] = 0.0
                d["last_seen"] = to_iso(now)
            continue

        # Battery drain / small recovery when idle
        battery = d.get("battery_percent")
        if battery is None:
            battery = 50
        if d["status"] == "flying":
            battery = max(0, battery - random.randint(0, 2))
            d["altitude_m"] = round(max(5.0, (d.get("altitude_m") or 30) + random.uniform(-2, 2)), 1)
            # Keep drifting so the flight path lengthens on the map (~150–250 m/step)
            d["lat"] = round((d.get("lat") or -34.60) + random.uniform(-0.0020, 0.0020), 5)
            d["lon"] = round((d.get("lon") or -58.38) + random.uniform(-0.0020, 0.0020), 5)
        else:
            battery = min(100, battery + random.randint(0, 1))
            d["altitude_m"] = 0.0

        d["battery_percent"] = battery
        d["last_seen"] = to_iso(now)

        # Random status flip between idle/flying (rare)
        if random.random() < 0.08:
            d["status"] = "flying" if d["status"] == "idle" else "idle"

        # Append history (keep last 10)
        history = d.get("history") or []
        history.append(
            {
                "ts": to_iso(now),
                "battery_percent": d["battery_percent"],
                "status": d["status"],
                "altitude_m": d.get("altitude_m"),
                "lat": d.get("lat"),
                "lon": d.get("lon"),
            }
        )
        d["history"] = history[-10:]

        # Mark offline if battery hits 0
        if battery <= 0:
            d["status"] = "offline"
            d["battery_percent"] = None
            d["last_seen"] = to_iso(now - timedelta(minutes=6))

    save_drones(drones)


def _loop(interval_sec: float = 15.0) -> None:
    while not _stop.is_set():
        try:
            tick_once()
        except Exception:
            pass
        _stop.wait(interval_sec)


def start_simulator(interval_sec: float = 15.0) -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, args=(interval_sec,), daemon=True)
    _thread.start()


def stop_simulator() -> None:
    _stop.set()
