"""Shared fixtures for SkyWatch Pilot API tests."""

import os
import sys
from pathlib import Path

# Use the real user Playwright browsers (not sandbox temp path)
_ms_playwright = Path.home() / "AppData" / "Local" / "ms-playwright"
if _ms_playwright.exists():
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(_ms_playwright))

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

pytest_plugins = ("pytest_playwright",)


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """
    Local practice: show the browser + slow actions so you can follow the UI.
    CI / headless: set CI=1 (GitHub Actions) or SKYWATCH_E2E_HEADLESS=1.
    Optional: SKYWATCH_E2E_SLOWMO=800 for slower, 0 for no delay.
    """
    if os.environ.get("CI") or os.environ.get("SKYWATCH_E2E_HEADLESS") == "1":
        return browser_type_launch_args

    slow_mo = int(os.environ.get("SKYWATCH_E2E_SLOWMO", "500"))
    return {
        **browser_type_launch_args,
        "headless": False,
        "slow_mo": slow_mo,
    }


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Fresh Flask test client; isolated SQLite DB; simulator off; drones reset."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("SKYWATCH_RESET_ON_START", "1")
    monkeypatch.setenv("SKYWATCH_SIM", "0")
    # Keep seed JSON from repo data/
    monkeypatch.delenv("SKYWATCH_DATA_DIR", raising=False)

    from app.db import reset_engine
    from app import create_app
    from app.store import bootstrap_database

    reset_engine()
    bootstrap_database(force_reset_drones=True, reset_eng=True)

    app = create_app(start_sim=False)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def pilot_token(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "pilot@demo.com", "password": "demo123"},
    )
    assert r.status_code == 200
    return r.get_json()["token"]


@pytest.fixture()
def pilot2_token(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "pilot2@demo.com", "password": "demo123"},
    )
    assert r.status_code == 200
    return r.get_json()["token"]
