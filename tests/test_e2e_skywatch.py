"""Phase 4 — Playwright E2E for SkyWatch Pilot UI."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
E2E_PORT = 8081
BASE_URL = f"http://127.0.0.1:{E2E_PORT}"


@pytest.fixture(scope="module")
def skywatch_server(tmp_path_factory):
    """Start Flask app on 8081 with isolated data dir (no clash with manual 8080)."""
    import shutil

    data_src = ROOT / "data"
    data_dir = tmp_path_factory.mktemp("skywatch-e2e-data")
    shutil.copy(data_src / "users.json", data_dir / "users.json")
    shutil.copy(data_src / "drones_seed.json", data_dir / "drones_seed.json")

    env = os.environ.copy()
    env["SKYWATCH_PORT"] = str(E2E_PORT)
    env["SKYWATCH_SIM"] = "0"
    env["SKYWATCH_DATA_DIR"] = str(data_dir)
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(Path.home() / "AppData" / "Local" / "ms-playwright")

    proc = subprocess.Popen(
        [sys.executable, "-m", "app"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            import urllib.request

            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=1):
                break
        except OSError:
            time.sleep(0.3)
    else:
        proc.kill()
        pytest.fail(f"SkyWatch server did not start on port {E2E_PORT}")

    try:
        import urllib.request

        req = urllib.request.Request(f"{BASE_URL}/api/v1/admin/reset-seed", method="POST")
        urllib.request.urlopen(req, timeout=3)
    except OSError:
        pass

    yield BASE_URL
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _login(page, base_url: str):
    page.goto(f"{base_url}/login")
    page.get_by_test_id("login-email").fill("pilot@demo.com")
    page.get_by_test_id("login-password").fill("demo123")
    page.get_by_test_id("login-submit").click()
    page.wait_for_url("**/drones")


@pytest.mark.e2e
def test_login_opens_drones_page(skywatch_server, page):
    _login(page, skywatch_server)
    assert page.get_by_test_id("drones-table").is_visible()
    assert page.get_by_test_id("drone-row-drn_01").is_visible()


@pytest.mark.e2e
def test_alerts_nav_badge_shows_count(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    badge = page.get_by_test_id("alerts-nav-badge")
    badge.wait_for(state="visible", timeout=10000)
    count = int(badge.inner_text().strip())
    assert count >= 1


@pytest.mark.e2e
def test_alerts_page_lists_issues(skywatch_server, page):
    # Fresh seed so Bravo/Charlie alerts are present
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-alerts").click()
    page.wait_for_url("**/alerts")
    page.get_by_test_id("alert-item-alert_drn_02_battery").wait_for(state="visible", timeout=10000)
    assert page.get_by_test_id("alert-item-alert_drn_03_offline").is_visible()
    assert page.get_by_test_id("alert-item-alert_drn_03_geofence").is_visible()


@pytest.mark.e2e
def test_acknowledge_removes_alert_from_ui(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-alerts").click()
    page.wait_for_url("**/alerts")

    bravo = page.get_by_test_id("alert-item-alert_drn_02_battery")
    bravo.wait_for(state="visible")
    page.get_by_test_id("ack-alert_drn_02_battery").click()
    bravo.wait_for(state="hidden", timeout=10000)

    # Still on Active tab — other alerts remain
    assert page.get_by_test_id("view-active").is_visible()
    assert page.get_by_test_id("alert-item-alert_drn_03_offline").is_visible()

    # Acknowledgement lands in History tab
    page.get_by_test_id("tab-history").click()
    page.get_by_test_id("view-history").wait_for(state="visible")
    page.get_by_test_id("history-item-alert_drn_02_battery").wait_for(state="visible")
    assert page.get_by_test_id("history-acked-label").first.is_visible()


@pytest.mark.e2e
def test_login_wrong_password_shows_error(skywatch_server, page):
    page.goto(f"{skywatch_server}/login")
    page.get_by_test_id("login-email").fill("pilot@demo.com")
    page.get_by_test_id("login-password").fill("wrong-password")
    page.get_by_test_id("login-submit").click()
    err = page.get_by_test_id("login-error")
    err.wait_for(state="visible")
    assert "Wrong" in err.inner_text() or "wrong" in err.inner_text().lower()


@pytest.mark.e2e
def test_map_page_shows_fleet_and_markers(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-map").click()
    page.wait_for_url("**/map")

    page.get_by_test_id("fleet-map").wait_for(state="visible")
    page.get_by_test_id("map-legend").wait_for(state="visible")
    page.get_by_test_id("marker-drn_01").wait_for(state="visible", timeout=10000)
    assert page.get_by_test_id("marker-drn_02").is_visible()
    assert page.get_by_test_id("marker-drn_03").is_visible()


@pytest.mark.e2e
def test_map_shows_flight_path_for_flying_drone(skywatch_server, page):
    """Alpha (flying) should have a Leaflet polyline path on the map."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-map").click()
    page.wait_for_url("**/map")
    page.get_by_test_id("marker-drn_01").wait_for(state="visible", timeout=10000)

    # Leaflet draws SVG paths for polylines
    paths = page.locator(".leaflet-overlay-pane path")
    assert paths.count() >= 1


@pytest.mark.e2e
def test_map_marker_opens_detail(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-map").click()
    page.wait_for_url("**/map")

    page.get_by_test_id("marker-drn_01").wait_for(state="visible", timeout=10000)
    page.get_by_test_id("marker-drn_01").click()
    page.get_by_role("link", name="Open detail →").click()
    page.wait_for_url("**/drones/drn_01")
    page.get_by_test_id("drone-detail").wait_for(state="visible")
    page.locator("#drone-name").filter(has_text="Alpha").wait_for(timeout=10000)
    assert "Alpha" in page.locator("#drone-name").inner_text()


@pytest.mark.e2e
def test_filter_status_flying_on_list(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("filter-bar").wait_for(state="visible")
    page.get_by_test_id("filter-status").select_option("flying")

    assert page.get_by_test_id("drone-row-drn_01").is_visible()
    assert page.get_by_test_id("drone-row-drn_02").count() == 0
    assert page.get_by_test_id("drone-row-drn_03").count() == 0
    assert "Showing 1 of 3" in page.get_by_test_id("filter-count").inner_text()


@pytest.mark.e2e
def test_filter_alerts_only_on_list(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("filter-alerts").select_option("alert")

    assert page.get_by_test_id("drone-row-drn_02").is_visible()  # Bravo low battery
    assert page.get_by_test_id("drone-row-drn_03").is_visible()  # Charlie offline + geofence
    assert page.get_by_test_id("drone-row-drn_01").count() == 0
    assert page.get_by_test_id("alert-badge-drn_02").is_visible()
    assert "Showing 2 of 3" in page.get_by_test_id("filter-count").inner_text()


@pytest.mark.e2e
def test_filter_status_flying_on_map(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-map").click()
    page.wait_for_url("**/map")
    page.get_by_test_id("marker-drn_01").wait_for(state="visible", timeout=10000)

    page.get_by_test_id("filter-status").select_option("flying")
    page.get_by_test_id("marker-drn_01").wait_for(state="visible", timeout=5000)
    assert page.get_by_test_id("marker-drn_02").count() == 0
    assert page.get_by_test_id("marker-drn_03").count() == 0


@pytest.mark.e2e
def test_map_shows_geofence_zone(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-map").click()
    page.wait_for_url("**/map")
    page.get_by_test_id("fleet-map").wait_for(state="visible")
    # Leaflet polygon is an SVG path in the overlay pane
    page.locator(".leaflet-overlay-pane path.geofence-zone, .leaflet-overlay-pane path").first.wait_for(
        state="visible", timeout=10000
    )
    assert "geofence" in page.get_by_test_id("map-legend").inner_text().lower()
