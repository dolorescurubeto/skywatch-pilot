# SkyWatch Pilot — Product Spec v1

**Status:** Phases 1–5 done (API + pytest + Web UI + Playwright E2E + GitHub Actions CI).  
**Author:** Dolores Curubeto  
**Last updated:** 2026-07-20

---

## Summary

**SkyWatch Pilot** is a real web product for **drone pilots/operators** who need to monitor their own drones and receive alerts (low battery, offline). Data is **simulated** at first; hardware integration comes later.

---

## Target user

- **Pilot / operator** with their own account
- Owns **1–3 drones** initially (MVP)
- Needs at-a-glance status and actionable alerts
- Does **not** need fleet management for 50+ drones in v1

---

## MVP scope

| In v1 | Later (v2+) |
|-------|-------------|
| Login (demo users) | User registration |
| List drones | Map view |
| Drone detail | Real DJI / MQTT integration |
| Alerts | Mobile native app |
| Simulated telemetry | Multi-tenant / company roles |

---

## Screens (4)

### 1. Login

- Email + password
- **Enter** button
- Error states: wrong credentials, empty fields
- **Demo users only** in v1 (no sign-up)

**Demo account (v1):**

```json
{
  "email": "pilot@demo.com",
  "password": "demo123",
  "pilot_id": "pilot_001"
}
```

Optional second pilot for 403 tests: `pilot2@demo.com` / same password pattern.

---

### 2. My drones (home, after login)

| Column | Example |
|--------|---------|
| Name | Alpha |
| Status | flying / idle / offline |
| Battery | 78% |
| Last signal | 1 min ago |

- Row click → **Drone detail**
- Nav → **Alerts**
- **Log out**
- Visual badge if drone has active alert

---

### 3. Drone detail

- ID, name, current status
- Battery %, altitude, lat/lon (numbers only in v1 — no map)
- Short history (last 5–10 simulated readings)
- **Back** to list

---

### 4. Alerts

Active alerts for logged-in pilot only:

- `Drone-02 — Low battery (18%)`
- `Drone-03 — Offline (12 min)`

**Alert types:**

| Type | Rule |
|------|------|
| `LOW_BATTERY` | `battery_percent < 20` and not offline |
| `OFFLINE` | No telemetry for **> 5 minutes** |

Alerts auto-resolve in v1 when battery recovers or signal returns (simple logic).

---

## Simulated data (v1)

### Sample drones for `pilot_001`

| id | name | status | battery | last_seen |
|----|------|--------|---------|-----------|
| drn_01 | Alpha | flying | 78 | now |
| drn_02 | Bravo | idle | 18 | ~2 min ago |
| drn_03 | Charlie | offline | null | ~12 min ago |

### Simulator (backend)

- Every **10–30 seconds**: update battery, status, position (bounded random)
- Apply alert rules
- No real hardware in v1

---

## API (REST)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/health` | No | Smoke check |
| POST | `/api/v1/auth/login` | No | email + password → token |
| POST | `/api/v1/auth/logout` | Yes | Optional in v1 |
| GET | `/api/v1/drones` | Yes | Pilot's drones only |
| GET | `/api/v1/drones/{id}` | Yes | Detail; **403** if not owner's drone |
| GET | `/api/v1/alerts` | Yes | Pilot's active alerts |

**Status codes (same as portfolio RBAC):**

- **401** — missing or invalid token
- **403** — valid token but drone belongs to another pilot
- **200** — success

---

## Tech stack (proposed)

| Layer | Choice |
|-------|--------|
| Backend + API | Python Flask or FastAPI |
| Auth | Bearer token (like `ai-qa-portfolio` RBAC) |
| Data | JSON files → SQLite when needed |
| Frontend | Simple web (HTML + JS or Flask templates) |
| Simulator | Python background script or thread |
| API tests | pytest |
| UI tests | Playwright (Phase 4) |
| CI | GitHub Actions (Phase 5) |

---

## Build phases

| Phase | Deliverable |
|-------|-------------|
| **1** | API + login + fake data + simulator |
| **2** | pytest: login, drones, alerts, 401/403 |
| **3** | Web UI: login → list → detail → alerts |
| **4** | Playwright: login flow + alert visible on UI |
| **5** | GitHub repo + CI |

**Note:** QA automation learning (portfolio Bloque 2–3) can continue in parallel. Start SkyWatch when ready — say *"arrancamos SkyWatch Fase 1"*.

---

## Suggested repo layout (when coding starts)

```
skywatch-pilot/
  skywatch-pilot-SPEC-v1.md   ← this file
  app/                        ← API + auth
  data/                       ← users, drones seed JSON
  simulator/                  ← telemetry simulator
  web/                        ← frontend
  tests/                      ← pytest
  requirements.txt
  README.md
```

---

## Interview / CV line (English)

> "SkyWatch Pilot — web app for drone operators with authentication, simulated telemetry, and alert rules (low battery, offline); API regression covered by pytest."

---

## Decisions locked for v1

- [x] Product name: **SkyWatch Pilot**
- [x] User: pilot / operator
- [x] Login: yes (demo users, no registration)
- [x] Screens: login, drone list, detail, alerts
- [x] Data: simulated
- [x] Platform: web browser
- [x] Map view (Leaflet) — Phase map feature
- [x] Real drones: no (v2)

---

## Open questions (when starting implementation)

- Flask vs FastAPI (default recommendation: **Flask** — matches portfolio)
- English vs Spanish UI (pilot market: consider **English** UI for USA jobs)
- Second demo pilot for RBAC-style tests: yes/no
