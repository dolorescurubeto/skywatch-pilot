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

from app import create_app  # noqa: E402
from app.store import reset_drones_from_seed  # noqa: E402


@pytest.fixture()
def client():
    """Fresh Flask test client; simulator off; drones reset to seed."""
    reset_drones_from_seed()
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
