#!/bin/bash
# Application Tracker — double-click launcher (macOS).
# First run creates the environment; after that it just starts the app.
cd "$(dirname "$0")"

# Already running? Just open it.
if curl -s http://127.0.0.1:8765/api/health >/dev/null 2>&1; then
  open http://127.0.0.1:8765
  exit 0
fi

if [ ! -d .venv ]; then
  echo "First run — setting things up (about a minute)…"
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r requirements.txt
fi

exec .venv/bin/python run.py
