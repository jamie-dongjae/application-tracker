#!/usr/bin/env python3
"""Generate demo/index.html from static/index.html.

The demo page is the real page with three mechanical changes: a " — demo"
title, asset paths prefixed with static/ (Pages serves the repo tree), and
the API shim loaded before any module script. Generating it kills the drift
that once shipped a demo without half the UI.

    python scripts/build_demo.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHIM_TAG = '  <script src="shim.js"></script>\n'


def build() -> str:
    html = (ROOT / "static" / "index.html").read_text()
    html = html.replace("<title>Application Tracker</title>",
                        "<title>Application Tracker — demo</title>")
    html = html.replace('href="css/app.css"', 'href="static/css/app.css"')
    html = html.replace('src="vendor/', 'src="static/vendor/')
    html = html.replace('src="js/main.js"', 'src="static/js/main.js"')
    # Shim must be installed before any module script evaluates.
    marker = '  <link href="static/css/app.css" rel="stylesheet">\n'
    if marker not in html:
        raise SystemExit("build_demo: css link marker not found — static/index.html changed shape")
    html = html.replace(marker, marker + SHIM_TAG)
    return html


def main() -> None:
    out = ROOT / "demo" / "index.html"
    out.write_text(build())
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
