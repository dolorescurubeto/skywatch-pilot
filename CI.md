# Continuous Integration

Every push / PR to `main` runs:

| Job | What |
|-----|------|
| **API pytest** | 19 tests (login, drones, alerts, acknowledge, 401/403) |
| **Playwright E2E** | 7 browser tests (login, badge, alerts, ack, map) |

## Local commands (same as CI)

```powershell
cd C:\Users\dell\skywatch-pilot
.\venv\Scripts\Activate.ps1
pytest tests\ -v
pytest tests\test_e2e_skywatch.py -m e2e -v
```

## Interview line

> "SkyWatch Pilot has GitHub Actions CI — API regression and Playwright E2E run on every push to main."
