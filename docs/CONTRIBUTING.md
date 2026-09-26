# Contributing

Small project, small rules. PRs welcome.

## Dev setup

```bash
git clone https://github.com/jamie-dongjae/application-tracker && cd application-tracker
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Python ≥ 3.10 (CI tests 3.10 and 3.12). The frontend has no build step — edit
`static/` and reload; the server sends `no-cache` for modules.

## Test principles

- **Everything runs offline.** Network-shaped behavior (ATS parsers, IMAP,
  geocoding) is tested against committed fixtures or monkeypatched at the
  module boundary — see `tests/test_mail_sync_api.py` for the pattern.
- **Fictional data only.** No real companies-as-personal-history, no real
  email addresses, no personal names anywhere in tests or sample data.
- Tests that touch `settings.json` / ledgers get an isolated
  `TRACKER_DATA_DIR` via the autouse monkeypatch fixture pattern in
  `tests/test_sync_import.py`.
- CI fails the build if a real workbook ever lands in the repo; `data/` is
  gitignored and must stay that way.

## Conventions worth knowing before a PR

- **Store owns consistency.** Status ↔ v4-field sync and field normalization
  happen inside `ExcelStore` (`_sync_after_merge`, `_clean`) — never in
  routers or the frontend. If you add a write path, it inherits these for free;
  don't duplicate them.
- **Never guess on imports.** The matcher skips ambiguous records; keep that
  property in anything that feeds `apply_packet`.
- **`stage_reached` is monotonic.** Nothing may lower it.
- **Design tokens over hex.** Colors come from the CSS custom properties in
  `app.css`; charts read them via `chartTokens()`, JS effects via
  `getComputedStyle`. `backdrop-filter` goes on container surfaces only —
  cards use gradient pseudo-glass.
- Frontend is vanilla ES modules; no dependencies, no bundler. Keep it that way.
- Commit messages: plain prose, present tense, say why.

## Regenerating demo artifacts

```bash
python scripts/make_sample_data.py --json-only   # demo/sample-data.json
python scripts/build_demo.py                     # demo/index.html from static/index.html
```

Both are also run by CI/Pages, so drift self-heals — but committing the
regenerated files keeps local demo browsing honest.
