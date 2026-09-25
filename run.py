#!/usr/bin/env python3
"""Launch Application Tracker: pick a free port, start the server, open the browser.

    python run.py [--port 8765] [--data-dir PATH] [--xlsx PATH] [--no-browser]
"""
from __future__ import annotations

import argparse
import fcntl
import os
import socket
import threading
import time
import urllib.request
import webbrowser

LOCK_PATH = "/tmp/application-tracker.lock"


def bind_free_port(start: int) -> socket.socket:
    """Bind and hold a socket so nothing can grab the port before uvicorn does."""
    for port in range(start, start + 50):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Mirror uvicorn's bind semantics: a port in TIME_WAIT from a
        # recent restart is still usable, so don't drift away from it.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return sock
        except OSError:
            sock.close()
    raise SystemExit(f"no free port in {start}–{start + 49}")


def wait_until_healthy(url: str, attempts: int) -> bool:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def open_when_ready(url: str) -> None:
    # Cold starts can be slow; never open the browser onto a dead server.
    if wait_until_healthy(url, attempts=120):
        webbrowser.open(url)
    else:
        print(f"server did not become ready; open {url} manually once it is up")


def defer_to_running_instance(start_port: int) -> None:
    """Another launch is already under way: wait for it, show it, and bow out."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        for port in range(start_port, start_port + 10):
            url = f"http://127.0.0.1:{port}"
            try:
                with urllib.request.urlopen(f"{url}/api/health", timeout=1):
                    webbrowser.open(url)
                    return
            except OSError:
                continue
        time.sleep(0.5)
    print("another instance is starting but never became ready; check /tmp/application-tracker.log")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Application Tracker job tracker locally.")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--data-dir", help="directory for tracker.xlsx, caches, backups")
    parser.add_argument("--xlsx", help="explicit path to the tracker workbook")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if args.data_dir:
        os.environ["TRACKER_DATA_DIR"] = args.data_dir
    if args.xlsx:
        os.environ["TRACKER_XLSX"] = args.xlsx

    import uvicorn

    from tracker.config import DEFAULT_PORT

    lock = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        if not args.no_browser:
            defer_to_running_instance(args.port or DEFAULT_PORT)
        return

    sock = bind_free_port(args.port or DEFAULT_PORT)
    port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    print(f"Application Tracker → {url}", flush=True)
    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    uvicorn.run("tracker.main:app", host="127.0.0.1", port=port,
                fd=sock.fileno(), log_level="warning")


if __name__ == "__main__":
    main()
