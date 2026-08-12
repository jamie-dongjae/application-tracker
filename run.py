#!/usr/bin/env python3
"""Launch Waypoint: pick a free port, start the server, open the browser.

    python run.py [--port 8765] [--data-dir PATH] [--xlsx PATH] [--no-browser]
"""
from __future__ import annotations

import argparse
import os
import socket
import threading
import time
import urllib.request
import webbrowser


def find_free_port(start: int) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit(f"no free port in {start}–{start + 49}")


def open_when_ready(url: str) -> None:
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1):
                break
        except OSError:
            time.sleep(0.2)
    webbrowser.open(url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Waypoint job tracker locally.")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--data-dir", help="directory for tracker.xlsx, caches, backups")
    parser.add_argument("--xlsx", help="explicit path to the tracker workbook")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if args.data_dir:
        os.environ["WAYPOINT_DATA_DIR"] = args.data_dir
    if args.xlsx:
        os.environ["WAYPOINT_XLSX"] = args.xlsx

    import uvicorn

    from waypoint.config import DEFAULT_PORT

    port = args.port or find_free_port(DEFAULT_PORT)
    url = f"http://127.0.0.1:{port}"
    print(f"Waypoint → {url}")
    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    uvicorn.run("waypoint.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
