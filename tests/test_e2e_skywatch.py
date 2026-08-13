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
    """Start Flask app on 8081 with isolated SQLite DB (no clash with manual 8080)."""
    import shutil

    data_src = ROOT / "data"
    data_dir = tmp_path_factory.mktemp("skywatch-e2e-data")
    shutil.copy(data_src / "users.json", data_dir / "users.json")
    shutil.copy(data_src / "drones_seed.json", data_dir / "drones_seed.json")
    db_path = data_dir / "e2e.db"

    env = os.environ.copy()
    env["SKYWATCH_PORT"] = str(E2E_PORT)
    env["SKYWATCH_SIM"] = "0"
    env["SKYWATCH_DATA_DIR"] = str(data_dir)
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["SKYWATCH_RESET_ON_START"] = "1"
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

    import urllib.request

    seeded = False
    for _ in range(10):
        try:
            req = urllib.request.Request(f"{BASE_URL}/api/v1/admin/reset-seed", method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    seeded = True
                    break
        except OSError:
            time.sleep(0.4)
    if not seeded:
        proc.kill()
        pytest.fail("Could not reset seed before E2E tests")

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
    page.get_by_test_id("drone-row-drn_01").wait_for(state="visible", timeout=10000)


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
def test_acknowledge_all_alerts_shows_empty(skywatch_server, page):
    import urllib.request
    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)
    _login(page, skywatch_server)
    page.get_by_test_id("nav-alerts").click()
    page.wait_for_url("**/alerts")
    for alert_id in (
        "alert_drn_02_battery",
        "alert_drn_03_offline",
        "alert_drn_03_geofence",
    ):
        item = page.get_by_test_id(f"alert-item-{alert_id}")
        item.wait_for(state="visible", timeout=10000)
        page.get_by_test_id(f"ack-{alert_id}").click()
        item.wait_for(state="hidden", timeout=10000)
    page.get_by_test_id("alerts-empty").wait_for(state="visible", timeout=10000)

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
def test_login_empty_fields_shows_error(skywatch_server, page):
    page.goto(f"{skywatch_server}/login")
    page.get_by_test_id("login-email").fill("")
    page.get_by_test_id("login-password").fill("")
    page.locator("#login-form").evaluate("f => f.setAttribute('novalidate', '')")
    page.get_by_test_id("login-submit").click()
    err = page.get_by_test_id("login-error")
    err.filter(has_text="required").wait_for(timeout=5000)
    assert "required" in err.inner_text().lower()

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
def test_filter_flying_and_search_alpha(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("filter-bar").wait_for(state="visible")
    page.get_by_test_id("filter-status").select_option("flying")
    page.get_by_test_id("filter-search").fill("alpha")

    assert page.get_by_test_id("drone-row-drn_01").is_visible()
    assert page.get_by_test_id("drone-row-drn_02").count() == 0
    assert page.get_by_test_id("drone-row-drn_03").count() == 0
    assert "Showing 1 of 3" in page.get_by_test_id("filter-count").inner_text()

@pytest.mark.e2e
def test_drones_without_login_redirects_to_login(skywatch_server, page):
    page.goto(f"{skywatch_server}/drones")
    page.wait_for_url("**/login")
    page.get_by_test_id("login-form").wait_for(state="visible")

@pytest.mark.e2e
def test_alerts_without_login_redirects_to_login(skywatch_server, page):
    page.goto(f"{skywatch_server}/alerts")
    page.wait_for_url("**/login")
    page.get_by_test_id("login-form").wait_for(state="visible")
  

@pytest.mark.e2e
def test_filter_status_offline_on_list(skywatch_server, page):
    """PRACTICE B: Offline on list → only Charlie."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("filter-bar").wait_for(state="visible")
    page.get_by_test_id("filter-status").select_option("offline")

    assert page.get_by_test_id("drone-row-drn_03").is_visible()
    assert page.get_by_test_id("drone-row-drn_01").count() == 0
    assert page.get_by_test_id("drone-row-drn_02").count() == 0
    assert "Showing 1 of 3" in page.get_by_test_id("filter-count").inner_text()


@pytest.mark.e2e
def test_filter_status_offline_on_map(skywatch_server, page):
    """PRACTICE C: Offline on map → only Charlie marker."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-map").click()
    page.wait_for_url("**/map")
    page.get_by_test_id("filter-status").select_option("offline")

    assert page.get_by_test_id("marker-drn_03").is_visible()
    assert page.get_by_test_id("marker-drn_01").count() == 0
    assert page.get_by_test_id("marker-drn_02").count() == 0
    assert "Showing 1 of 3" in page.get_by_test_id("filter-count").inner_text()


@pytest.mark.e2e
def test_charlie_marker_opens_detail(skywatch_server, page):
    """PRACTICE D: map → click Charlie → Open detail → see Charlie."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-map").click()
    page.wait_for_url("**/map")

    # Click en el marcador (igual idea que .click() en JS)
    page.get_by_test_id("marker-drn_03").wait_for(state="visible", timeout=10000)
    page.get_by_test_id("marker-drn_03").click()

    # Click en el link del popup
    page.get_by_role("link", name="Open detail →").click()

    page.wait_for_url("**/drones/drn_03")
    page.get_by_test_id("drone-detail").wait_for(state="visible")
    page.locator("#drone-name").filter(has_text="Charlie").wait_for(timeout=10000)
    assert "Charlie" in page.locator("#drone-name").inner_text()


@pytest.mark.e2e
def test_charlie_row_opens_detail(skywatch_server, page):
    """PRACTICE E: My drones → click Charlie row → detail."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)

    page.get_by_test_id("drone-row-drn_03").click()

    page.wait_for_url("**/drones/drn_03")
    page.get_by_test_id("drone-detail").wait_for(state="visible")
    page.locator("#drone-name").filter(has_text="Charlie").wait_for(timeout=10000)
    assert "Charlie" in page.locator("#drone-name").inner_text()

@pytest.mark.e2e
def test_detail_back_returns_to_drones_list(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)

    page.get_by_test_id("drone-row-drn_01").click()
    page.wait_for_url("**/drones/drn_01")
    page.get_by_test_id("back-link").click()
    page.wait_for_url("**/drones")
    page.get_by_test_id("drone-row-drn_01").wait_for(state="visible")
    

@pytest.mark.e2e
def test_search_filters_charlie(skywatch_server, page):
    """PRACTICE F: type in Search → only Charlie row."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)

    page.get_by_test_id("filter-search").fill("charlie")

    assert page.get_by_test_id("drone-row-drn_03").is_visible()
    assert page.get_by_test_id("drone-row-drn_01").count() == 0
    assert page.get_by_test_id("drone-row-drn_02").count() == 0
    assert "Showing 1 of 3" in page.get_by_test_id("filter-count").inner_text()


@pytest.mark.e2e
def test_ack_charlie_offline_goes_to_history(skywatch_server, page):
    """PRACTICE G: Alerts → Acknowledge Charlie OFFLINE → History."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-alerts").click()
    page.wait_for_url("**/alerts")

    offline = page.get_by_test_id("alert-item-alert_drn_03_offline")
    offline.wait_for(state="visible")
    page.get_by_test_id("ack-alert_drn_03_offline").click()
    offline.wait_for(state="hidden", timeout=10000)

    page.get_by_test_id("tab-history").click()
    page.get_by_test_id("view-history").wait_for(state="visible")
    page.get_by_test_id("history-item-alert_drn_03_offline").wait_for(state="visible")

@pytest.mark.e2e
def test_ack_charlie_geofence_goes_to_history(skywatch_server, page):
    """PRACTICE h: Alerts → Acknowledge Charlie geofence → History."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-alerts").click()
    page.wait_for_url("**/alerts")

    geofence = page.get_by_test_id("alert-item-alert_drn_03_geofence")
    geofence.wait_for(state="visible")
    page.get_by_test_id("ack-alert_drn_03_geofence").click()
    geofence.wait_for(state="hidden", timeout=10000)

    page.get_by_test_id("tab-history").click()
    page.get_by_test_id("view-history").wait_for(state="visible")
    page.get_by_test_id("history-item-alert_drn_03_geofence").wait_for(state="visible")



@pytest.mark.e2e
def test_profile_shows_demo_pilot(skywatch_server, page):
    """PRACTICE H: click Demo Pilot → profile name + email."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)

    # Click en el nombre del piloto (nav)
    page.get_by_test_id("nav-profile").click()
    page.wait_for_url("**/profile")

    # Completá vos:
    # 1) pilot-profile visible
    # 2) #profile-name contiene "Demo Pilot"
    # 3) profile-email == "pilot@demo.com"
    # Pista: mirá test_profile_page_shows_pilot_info
    raise NotImplementedError("Completá asserts del profile")


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
def test_filter_alerts_only_and_search_charlie(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("filter-alerts").select_option("alert")
    page.get_by_test_id("filter-search").fill("charlie")
    assert page.get_by_test_id("drone-row-drn_03").is_visible()
    assert page.get_by_test_id("drone-row-drn_01").count() == 0
    assert page.get_by_test_id("drone-row-drn_02").count() == 0


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


@pytest.mark.e2e
def test_profile_page_shows_pilot_info(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-profile").click()
    page.wait_for_url("**/profile")

    page.get_by_test_id("pilot-profile").wait_for(state="visible")
    assert "Demo Pilot" in page.locator("#profile-name").inner_text()
    assert page.get_by_test_id("profile-email").inner_text() == "pilot@demo.com"
    assert page.get_by_test_id("profile-pilot-id").inner_text() == "pilot_001"
    assert page.get_by_test_id("profile-license").inner_text()
    assert page.get_by_test_id("profile-last-login").inner_text() != "—"
    assert int(page.locator("#fleet-total").inner_text()) == 3


@pytest.mark.e2e
def test_search_filters_drone_by_name(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("filter-search").fill("alpha")

    assert page.get_by_test_id("drone-row-drn_01").is_visible()
    assert page.get_by_test_id("drone-row-drn_02").count() == 0
    assert page.get_by_test_id("drone-row-drn_03").count() == 0
    assert "Showing 1 of 3" in page.get_by_test_id("filter-count").inner_text()


@pytest.mark.e2e
def test_export_history_csv_button(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-alerts").click()
    page.wait_for_url("**/alerts")
    page.get_by_test_id("ack-alert_drn_02_battery").click()
    page.get_by_test_id("alert-item-alert_drn_02_battery").wait_for(state="hidden", timeout=10000)

    page.get_by_test_id("tab-history").click()
    page.get_by_test_id("view-history").wait_for(state="visible")
    page.get_by_test_id("history-item-alert_drn_02_battery").wait_for(state="visible")

    with page.expect_download() as download_info:
        page.get_by_test_id("export-history-btn").click()
    download = download_info.value
    assert download.suggested_filename.endswith(".csv")


@pytest.mark.e2e
def test_change_bravo_status_to_flying(skywatch_server, page):
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("drone-row-drn_02").click()
    page.wait_for_url("**/drones/drn_02")
    page.get_by_test_id("drone-detail").wait_for(state="visible")
    page.get_by_test_id("detail-status").wait_for(state="visible")
    assert page.get_by_test_id("detail-status").inner_text() == "idle"

    page.get_by_test_id("status-flying").click()
    page.get_by_test_id("detail-status").filter(has_text="flying").wait_for(timeout=10000)
    assert page.get_by_test_id("detail-status").inner_text() == "flying"


@pytest.mark.e2e
def test_change_alpha_status_to_idle(skywatch_server, page):
    """PRACTICE I: Alpha detail → Set idle → status becomes idle."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)

    # Abrir detalle de Alpha (en seed suele estar flying)
    page.get_by_test_id("drone-row-drn_01").click()
    page.wait_for_url("**/drones/drn_01")
    page.get_by_test_id("drone-detail").wait_for(state="visible")
    page.get_by_test_id("detail-status").wait_for(state="visible")

    assert page.get_by_test_id("detail-status").inner_text() == "flying"

    page.get_by_test_id("status-idle").click()
    page.get_by_test_id("detail-status").filter(has_text="idle").wait_for(timeout=10000)
    assert page.get_by_test_id("detail-status").inner_text() == "idle"


@pytest.mark.e2e
def test_logout_returns_to_login(skywatch_server, page):
    """Log out clears session and lands on login."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("drones-table").wait_for(state="visible")
    page.get_by_test_id("logout-btn").click()
    page.wait_for_url("**/login")
    page.get_by_test_id("login-form").wait_for(state="visible")


@pytest.mark.e2e
def test_search_no_match_shows_empty(skywatch_server, page):
    """Search with no hits shows empty filter row."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("filter-search").fill("zzzz-no-drone")
    page.get_by_test_id("filter-empty").wait_for(state="visible", timeout=10000)
    assert page.get_by_test_id("drone-row-drn_01").count() == 0
    assert "Showing 0 of 3" in page.get_by_test_id("filter-count").inner_text()


@pytest.mark.e2e
def test_clear_search_restores_all_drones(skywatch_server, page):
    """Clearing search brings the full fleet back."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    search = page.get_by_test_id("filter-search")
    search.fill("charlie")
    page.get_by_test_id("drone-row-drn_03").wait_for(state="visible")
    assert page.get_by_test_id("drone-row-drn_01").count() == 0

    search.fill("")
    page.get_by_test_id("drone-row-drn_01").wait_for(state="visible", timeout=10000)
    assert page.get_by_test_id("drone-row-drn_02").is_visible()
    assert page.get_by_test_id("drone-row-drn_03").is_visible()
    assert "Showing 3 of 3" in page.get_by_test_id("filter-count").inner_text()


@pytest.mark.e2e
def test_history_empty_before_any_ack(skywatch_server, page):
    """History tab shows empty state when nothing was acknowledged."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-alerts").click()
    page.wait_for_url("**/alerts")
    page.get_by_test_id("alert-item-alert_drn_02_battery").wait_for(state="visible", timeout=10000)

    page.get_by_test_id("tab-history").click()
    page.get_by_test_id("view-history").wait_for(state="visible")
    page.get_by_test_id("history-empty").wait_for(state="visible")
    assert page.get_by_test_id("history-list").locator("li").count() == 0


@pytest.mark.e2e
def test_nav_map_and_back_to_drones(skywatch_server, page):
    """Nav: drones → map → drones keeps session."""
    import urllib.request

    req = urllib.request.Request(f"{skywatch_server}/api/v1/admin/reset-seed", method="POST")
    urllib.request.urlopen(req, timeout=3)

    _login(page, skywatch_server)
    page.get_by_test_id("nav-map").click()
    page.wait_for_url("**/map")
    page.get_by_test_id("fleet-map").wait_for(state="visible")
    page.get_by_test_id("marker-drn_01").wait_for(state="visible", timeout=10000)

    page.get_by_test_id("nav-drones").click()
    page.wait_for_url("**/drones")
    page.get_by_test_id("drone-row-drn_01").wait_for(state="visible", timeout=10000)
