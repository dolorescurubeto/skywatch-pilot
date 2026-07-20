"""SkyWatch Pilot — Flask API + Web UI (Phases 1–3)."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, g, jsonify, redirect, render_template, request, url_for

from app.alerts import (
    acknowledge_alert_for_pilot,
    compute_alerts_for_drone,
    compute_alerts_for_pilot,
    enrich_drone_list_item,
)
from app.auth import require_auth
from app.store import (
    find_user_by_email,
    get_acknowledged_ids,
    get_drone,
    load_drones,
    reset_drones_from_seed,
)
from simulator.telemetry import start_simulator

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

app = Flask(
    __name__,
    template_folder=str(WEB / "templates"),
    static_folder=str(WEB / "static"),
    static_url_path="/static",
)


# ---------- Web pages ----------


@app.get("/")
def home():
    return redirect(url_for("page_login"))


@app.get("/login")
def page_login():
    return render_template("login.html")


@app.get("/drones")
def page_drones():
    return render_template("drones.html")


@app.get("/drones/<drone_id>")
def page_drone_detail(drone_id: str):
    return render_template("detail.html")


@app.get("/alerts")
def page_alerts():
    return render_template("alerts.html")


@app.get("/map")
def page_map():
    return render_template("map.html")


# ---------- API ----------


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "skywatch-pilot"})


@app.post("/api/v1/auth/login")
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email or not password:
        return jsonify({"error": "validation_error", "message": "Email and password required"}), 400

    user = find_user_by_email(email)
    if not user or user["password"] != password:
        return jsonify({"error": "invalid_credentials", "message": "Wrong email or password"}), 401

    return jsonify(
        {
            "token": user["token"],
            "pilot_id": user["pilot_id"],
            "name": user["name"],
            "email": user["email"],
        }
    )


@app.post("/api/v1/auth/logout")
@require_auth
def logout():
    return jsonify({"ok": True})


@app.get("/api/v1/drones")
@require_auth
def list_drones():
    pilot_id = g.current_user["pilot_id"]
    drones = [
        enrich_drone_list_item(d, pilot_id=pilot_id)
        for d in load_drones()
        if d["pilot_id"] == pilot_id
    ]
    return jsonify({"count": len(drones), "drones": drones})


@app.get("/api/v1/drones/<drone_id>")
@require_auth
def drone_detail(drone_id: str):
    drone = get_drone(drone_id)
    if not drone:
        return jsonify({"error": "not_found", "message": "Drone not found"}), 404
    if drone["pilot_id"] != g.current_user["pilot_id"]:
        return jsonify({"error": "forbidden", "message": "Not your drone"}), 403
    pilot_id = g.current_user["pilot_id"]
    alerts = compute_alerts_for_drone(drone)
    acked = get_acknowledged_ids(pilot_id)
    alerts = [a for a in alerts if a["id"] not in acked]
    drone["alerts"] = alerts
    drone["has_alert"] = len(alerts) > 0
    return jsonify(drone)


@app.get("/api/v1/alerts")
@require_auth
def list_alerts():
    pilot_id = g.current_user["pilot_id"]
    alerts = compute_alerts_for_pilot(load_drones(), pilot_id)
    return jsonify({"count": len(alerts), "alerts": alerts})


@app.post("/api/v1/alerts/<alert_id>/acknowledge")
@require_auth
def acknowledge(alert_id: str):
    pilot_id = g.current_user["pilot_id"]
    match = acknowledge_alert_for_pilot(pilot_id, alert_id, load_drones())
    if not match:
        return jsonify({"error": "not_found", "message": "Alert not found or not yours"}), 404
    return jsonify({"ok": True, "acknowledged": match["id"]})


@app.post("/api/v1/admin/reset-seed")
def reset_seed():
    drones = reset_drones_from_seed()
    return jsonify({"ok": True, "count": len(drones)})


def create_app(start_sim: bool = True) -> Flask:
    reset_drones_from_seed()
    if start_sim:
        start_simulator(interval_sec=15.0)
    return app


if __name__ == "__main__":
    create_app(start_sim=True)
    # 0.0.0.0 so localhost and 127.0.0.1 both work in the browser
    app.run(host="0.0.0.0", port=8080, debug=True, use_reloader=False)
