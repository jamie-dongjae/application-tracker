#!/usr/bin/env python3
"""Start the tracker fully detached from the caller (for OS launcher apps).

If the server is already up, just opens the browser to it. Otherwise starts
run.py in its own session so it survives the launcher exiting (macOS .app
bundles kill their child process group on quit).
"""
import os
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# An instance may already be running (possibly on a drifted port).
for port in range(8765, 8775):
    url = f"http://127.0.0.1:{port}"
    try:
        with urllib.request.urlopen(url + "/api/health", timeout=0.4) as resp:
            if b'"ok":' in resp.read(200):
                if sys.platform == "darwin":
                    subprocess.run(["open", url], check=False)
                sys.exit(0)
    except OSError:
        continue

python = os.path.join(ROOT, ".venv", "bin", "python")
log = open("/tmp/application-tracker.log", "a")
subprocess.Popen([python, os.path.join(ROOT, "run.py")],
                 cwd=ROOT, start_new_session=True, stdout=log, stderr=log)
