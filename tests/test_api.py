"""Phase 2 — API tests: health, login, drones, alerts, 401/403."""

import pytest


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "ok"
    assert body["service"] == "skywatch-pilot"


def test_login_ok(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "pilot@demo.com", "password": "demo123"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["token"] == "pilot-001-demo-token"
    assert body["pilot_id"] == "pilot_001"
    assert body["email"] == "pilot@demo.com"


def test_login_wrong_password(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "pilot@demo.com", "password": "wrong"},
    )
    assert r.status_code == 401
    assert r.get_json()["error"] == "invalid_credentials"


def test_login_empty_fields(client):
    r = client.post("/api/v1/auth/login", json={"email": "", "password": ""})
    assert r.status_code == 400


def test_drones_requires_auth(client):
    r = client.get("/api/v1/drones")
    assert r.status_code == 401


def test_drones_list_for_pilot(client, pilot_token):
    r = client.get("/api/v1/drones", headers=auth_headers(pilot_token))
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 3
    ids = {d["id"] for d in body["drones"]}
    assert ids == {"drn_01", "drn_02", "drn_03"}
    # Pilot 2's drone must not appear
    assert "drn_10" not in ids


def test_flying_drone_includes_flight_path(client, pilot_token):
    r = client.get("/api/v1/drones", headers=auth_headers(pilot_token))
    drones = {d["id"]: d for d in r.get_json()["drones"]}
    alpha = drones["drn_01"]
    assert alpha["status"] == "flying"
    assert "flight_path" in alpha
    assert len(alpha["flight_path"]) >= 2
    assert "lat" in alpha["flight_path"][0]
    assert "lon" in alpha["flight_path"][0]


def test_drone_detail_ok(client, pilot_token):
    r = client.get("/api/v1/drones/drn_01", headers=auth_headers(pilot_token))
    assert r.status_code == 200
    body = r.get_json()
    assert body["name"] == "Alpha"
    assert body["status"] == "flying"
    assert "history" in body


def test_drone_detail_not_found(client, pilot_token):
    r = client.get("/api/v1/drones/drn_999", headers=auth_headers(pilot_token))
    assert r.status_code == 404


def test_drone_detail_forbidden_other_pilot(client, pilot_token):
    """pilot_001 cannot see pilot_002's drone (drn_10)."""
    r = client.get("/api/v1/drones/drn_10", headers=auth_headers(pilot_token))
    assert r.status_code == 403
    assert r.get_json()["error"] == "forbidden"


def test_patch_drone_status_idle_to_flying(client, pilot_token):
    headers = auth_headers(pilot_token)
    r = client.patch(
        "/api/v1/drones/drn_02/status",
        headers=headers,
        json={"status": "flying"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["drone"]["status"] == "flying"
    assert body["drone"]["altitude_m"] > 0

    detail = client.get("/api/v1/drones/drn_02", headers=headers).get_json()
    assert detail["status"] == "flying"


def test_patch_drone_status_invalid(client, pilot_token):
    r = client.patch(
        "/api/v1/drones/drn_01/status",
        headers=auth_headers(pilot_token),
        json={"status": "offline"},
    )
    assert r.status_code == 400


def test_patch_drone_status_forbidden(client, pilot_token):
    r = client.patch(
        "/api/v1/drones/drn_10/status",
        headers=auth_headers(pilot_token),
        json={"status": "idle"},
    )
    assert r.status_code == 403


def test_alerts_include_low_battery_and_offline(client, pilot_token):
    r = client.get("/api/v1/alerts", headers=auth_headers(pilot_token))
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] >= 2
    types = {a["type"] for a in body["alerts"]}
    assert "LOW_BATTERY" in types
    assert "OFFLINE" in types
    assert "GEOFENCE_BREACH" in types
    drone_ids = {a["drone_id"] for a in body["alerts"]}
    assert "drn_02" in drone_ids  # Bravo low battery
    assert "drn_03" in drone_ids  # Charlie offline + outside geofence


def test_geofence_endpoint_returns_polygon(client, pilot_token):
    r = client.get("/api/v1/geofence", headers=auth_headers(pilot_token))
    assert r.status_code == 200
    body = r.get_json()
    assert body["id"] == "zone_ba_centro"
    assert len(body["polygon"]) >= 3
    assert all(len(p) == 2 for p in body["polygon"])


def test_charlie_outside_geofence_alpha_inside(client, pilot_token):
    r = client.get("/api/v1/drones", headers=auth_headers(pilot_token))
    drones = {d["id"]: d for d in r.get_json()["drones"]}
    charlie_types = {a["type"] for a in drones["drn_03"]["alerts"]}
    alpha_types = {a["type"] for a in drones["drn_01"]["alerts"]}
    assert "GEOFENCE_BREACH" in charlie_types
    assert "GEOFENCE_BREACH" not in alpha_types
    assert drones["drn_03"]["has_alert"] is True


def test_alerts_requires_auth(client):
    r = client.get("/api/v1/alerts")
    assert r.status_code == 401


def test_logout_ok(client, pilot_token):
    r = client.post("/api/v1/auth/logout", headers=auth_headers(pilot_token))
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_bravo_has_alert_flag_on_list(client, pilot_token):
    r = client.get("/api/v1/drones", headers=auth_headers(pilot_token))
    drones = {d["id"]: d for d in r.get_json()["drones"]}
    assert drones["drn_02"]["has_alert"] is True
    assert drones["drn_01"]["has_alert"] is False


def test_acknowledge_alert_removes_from_list(client, pilot_token):
    headers = auth_headers(pilot_token)
    before = client.get("/api/v1/alerts", headers=headers).get_json()
    assert before["count"] >= 2
    alert_id = before["alerts"][0]["id"]

    r = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=headers)
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    after = client.get("/api/v1/alerts", headers=headers).get_json()
    assert after["count"] == before["count"] - 1
    assert alert_id not in {a["id"] for a in after["alerts"]}

    history = client.get("/api/v1/alerts/history", headers=headers).get_json()
    assert history["count"] >= 1
    assert history["history"][0]["id"] == alert_id
    assert "acknowledged_at" in history["history"][0]


def test_alerts_history_empty_before_ack(client, pilot_token):
    r = client.get("/api/v1/alerts/history", headers=auth_headers(pilot_token))
    assert r.status_code == 200
    assert r.get_json()["count"] == 0
    assert r.get_json()["history"] == []


def test_alerts_history_export_csv(client, pilot_token):
    headers = auth_headers(pilot_token)
    # Seed one history row via acknowledge
    before = client.get("/api/v1/alerts", headers=headers).get_json()
    alert_id = before["alerts"][0]["id"]
    client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=headers)

    r = client.get("/api/v1/alerts/history/export", headers=headers)
    assert r.status_code == 200
    assert "text/csv" in r.content_type
    text = r.get_data(as_text=True)
    assert "acknowledged_at" in text
    assert alert_id in text


def test_acknowledge_unknown_alert_404(client, pilot_token):
    r = client.post(
        "/api/v1/alerts/alert_does_not_exist/acknowledge",
        headers=auth_headers(pilot_token),
    )
    assert r.status_code == 404


def test_acknowledge_twice_returns_404(client, pilot_token):
    """Second acknowledge of the same alert is not found (already history)."""
    headers = auth_headers(pilot_token)
    before = client.get("/api/v1/alerts", headers=headers).get_json()
    alert_id = before["alerts"][0]["id"]

    first = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=headers)
    assert first.status_code == 200

    second = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=headers)
    assert second.status_code == 404
    assert second.get_json()["error"] == "not_found"


def test_export_history_csv_empty_still_has_header(client, pilot_token):
    """CSV export with no history still returns header row."""
    r = client.get(
        "/api/v1/alerts/history/export",
        headers=auth_headers(pilot_token),
    )
    assert r.status_code == 200
    assert "text/csv" in r.content_type
    text = r.get_data(as_text=True)
    lines = [ln for ln in text.strip().splitlines() if ln]
    assert len(lines) == 1
    assert "acknowledged_at" in lines[0]
    assert "drone_id" in lines[0]


def test_pilot2_list_excludes_pilot1_drones(client, pilot2_token):
    """pilot_002 only sees their own fleet (drn_10), not pilot_001 drones."""
    r = client.get("/api/v1/drones", headers=auth_headers(pilot2_token))
    assert r.status_code == 200
    body = r.get_json()
    ids = {d["id"] for d in body["drones"]}
    assert "drn_10" in ids
    assert "drn_01" not in ids
    assert "drn_02" not in ids
    assert "drn_03" not in ids
    assert body["count"] == len(ids)


def test_acknowledge_requires_auth(client):
    r = client.post("/api/v1/alerts/alert_drn_02_battery/acknowledge")
    assert r.status_code == 401

def test_acknowledge_geofence_alert_goes_to_history(client, pilot_token):
    headers = auth_headers(pilot_token)
    alert_id = "alert_drn_03_geofence"
    r = client.post("/api/v1/alerts/alert_drn_03_geofence/acknowledge",
                    headers=auth_headers(pilot_token),)
    assert r.status_code == 200

    after = client.get("/api/v1/alerts", headers=auth_headers(pilot_token))
    assert after.status_code == 200
    ids = {a["id"] for a in after.get_json()["alerts"]}
    assert "alert_drn_03_geofence" not in ids

    history = client.get("/api/v1/alerts/history", headers=auth_headers(pilot_token))
    assert history.status_code == 200
    row = next(h for h in history.get_json()["history"] if h["id"] == "alert_drn_03_geofence")
    assert row["type"] == "GEOFENCE_BREACH"
  


@pytest.mark.parametrize(
    "email,password,expected_status",
    [
        ("pilot@demo.com", "demo123", 200),
        ("pilot2@demo.com", "demo123", 200),
        ("nobody@demo.com", "demo123", 401),
    ],
    ids=["pilot1_ok", "pilot2_ok", "unknown_user"],
)
def test_login_parametrize(client, email, password, expected_status):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == expected_status


def test_me_requires_auth(client):
    r = client.get("/api/v1/me")
    assert r.status_code == 401


def test_me_profile_for_pilot(client, pilot_token):
    r = client.get("/api/v1/me", headers=auth_headers(pilot_token))
    assert r.status_code == 200
    body = r.get_json()
    assert body["email"] == "pilot@demo.com"
    assert body["name"] == "Demo Pilot"
    assert body["pilot_id"] == "pilot_001"
    assert body["role"] == "Pilot"
    assert body["license_id"]
    assert body["home_base"]
    assert body["last_login"] is not None
    assert body["fleet"]["total"] == 3
    assert body["active_alerts"] >= 1
    assert "password" not in body
    assert "token" not in body
