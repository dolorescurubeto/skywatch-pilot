"""Run: python -m app

Env:
  SKYWATCH_PORT — default 8080 (use 8081 for e2e)
  SKYWATCH_SIM  — set to 0 to disable simulator
"""

import os

from app import app, create_app

port = int(os.environ.get("SKYWATCH_PORT", "8080"))
start_sim = os.environ.get("SKYWATCH_SIM", "1") != "0"

create_app(start_sim=start_sim)
app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
