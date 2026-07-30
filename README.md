# SkyWatch Pilot

Web app for **drone pilots** — monitor your drones and get alerts (low battery, offline).

**Phase 1 (done):** Flask API + login + simulated data + background telemetry simulator.

## Demo login

| Email | Password |
|-------|----------|
| `pilot@demo.com` | `demo123` |
| `pilot2@demo.com` | `demo123` |

## Setup

```powershell
cd C:\Users\dell\skywatch-pilot
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run API

```powershell
cd C:\Users\dell\skywatch-pilot
.\venv\Scripts\Activate.ps1
python -m app
```

Server: http://127.0.0.1:8080

## Quick smoke tests (PowerShell)

**Health**

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
```

**Login**

```powershell
$login = Invoke-RestMethod -Method POST http://127.0.0.1:8080/api/v1/auth/login `
  -ContentType "application/json" `
  -Body '{"email":"pilot@demo.com","password":"demo123"}'
$token = $login.token
$token
```

**List drones**

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/v1/drones -Headers @{ Authorization = "Bearer $token" }
```

**Alerts**

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/v1/alerts -Headers @{ Authorization = "Bearer $token" }
```

**401 without token**

```powershell
try { Invoke-WebRequest http://127.0.0.1:8080/api/v1/drones } catch { $_.Exception.Response.StatusCode.value__ }
```

## API endpoints

| Method | Path | Auth |
|--------|------|------|
| GET | `/health` | No |
| POST | `/api/v1/auth/login` | No |
| POST | `/api/v1/auth/logout` | Yes |
| GET | `/api/v1/me` | Yes |
| GET | `/api/v1/drones` | Yes |
| GET | `/api/v1/drones/{id}` | Yes |
| PATCH | `/api/v1/drones/{id}/status` | Yes |
| GET | `/api/v1/alerts` | Yes |
| GET | `/api/v1/alerts/history` | Yes |
| GET | `/api/v1/alerts/history/export` | Yes |
| GET | `/api/v1/geofence` | Yes |
| POST | `/api/v1/admin/reset-seed` | No (dev) |

## Alert rules

- **LOW_BATTERY** — battery &lt; 20% and not offline
- **OFFLINE** — status offline or no telemetry for &gt; 5 minutes
- **GEOFENCE_BREACH** — drone lat/lon is outside the authorized flight zone

## Project layout

```
skywatch-pilot/
  skywatch-pilot-SPEC-v1.md
  app/           # Flask API, auth, alerts, store
  data/          # users + drone seed/state
  simulator/     # telemetry tick loop
  tests/         # Phase 2 — pytest
  requirements.txt
  README.md
```

## Database (SaaS Phase 1 — local, free)

SkyWatch uses **SQLAlchemy**. On your PC it stores data in SQLite at `data/skywatch.db` — **no cloud account, no payment**.

| Env var | Purpose |
|---------|---------|
| `DATABASE_URL` | Optional. Default = local SQLite (`data/skywatch.db`). |
| `SKYWATCH_RESET_ON_START=1` | Reseed drones on boot (tests / fresh demo). Leave `0` for normal local use. |
| `SKYWATCH_SIM=0` | Disable telemetry simulator |
| `SKYWATCH_DATA_DIR` | Folder with seed JSON (`users.json`, `drones_seed.json`) |

Seed JSON files bootstrap the DB the first time (or after `POST /api/v1/admin/reset-seed`).

### Optional deploy (still free)

`Procfile` + `render.yaml` start the app with **gunicorn** and **SQLite** (no paid Postgres). On Render’s free web tier the disk is ephemeral — fine for demos; your day-to-day work stays on local SQLite.

## Web UI (local)

```powershell
cd C:\Users\dell\skywatch-pilot
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app
```

Open in browser: **http://localhost:8080/login**

| Email | Password |
|-------|----------|
| `pilot@demo.com` | `demo123` |

Flow: Login → My drones → **Map** → Detail → Alerts → Acknowledge → Log out.

**Map:** http://localhost:8080/map — markers by status, flight paths, and a dashed **geofence** (authorized zone). Charlie starts outside → `GEOFENCE_BREACH`.

**Filters:** on **My drones** and **Map** — status, alerts, and **search by name/id**. Count shows `Showing X of Y`.

**Alerts:** tabs **Active** / **History**. History has **Export CSV**. New alerts show a **toast** notification while you browse.

**Profile:** click your name in the nav → `/profile` (email, license, home base, last login, fleet summary).

**Status control:** on drone detail, **Set idle** / **Set flying** (manual status change).

## Tests

**API only (default — Phase 2):**

```powershell
pytest tests\ -v
```

Expected: API + unit tests pass (e2e excluded by default via `-m "not e2e"` if needed).

**E2E Playwright (Phase 4) — one-time setup:**

```powershell
pip install -r requirements.txt
playwright install chromium
```

**Run E2E:**

```powershell
pytest tests\test_e2e_skywatch.py -m e2e -v
```

Starts the app on port **8081** automatically (so it does not conflict with your manual server on 8080).

## Product phases

| Phase | Status |
|-------|--------|
| 1 API + login + simulator | **Done** |
| 2 pytest API | **Done** |
| 3 Web UI | **Done** |
| 4 Playwright E2E | **Done** |
| 5 CI (GitHub Actions) | **Done** — see `CI.md` and `.github/workflows/ci.yml` |
| SaaS 1 — DB persistence (SQLite local) | **Done** (this machine; no payment) |
| SaaS 2 — real auth / tenants | Later |

## Spec

See `skywatch-pilot-SPEC-v1.md`.
