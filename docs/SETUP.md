# Setup

Everything the README's Quick Start glosses over.

## Requirements

- Python ≥ 3.10 (CI runs 3.10 and 3.12)
- Any modern browser. The app serves itself at `http://127.0.0.1:8765` — local only, nothing is exposed to your network.
- No database, no Node, no API keys. Excel itself is optional: the workbook is standard `.xlsx`, but the app reads and writes it with `openpyxl`.

## First run

**macOS** — double-click `start.command` (first time: right-click → Open). It creates `.venv/`, installs the five runtime dependencies, starts the server, and opens your browser once the app answers. Subsequent launches reuse everything and take a second.

**Windows** — double-click `start.bat`. Same behavior.

**Terminal**

```bash
git clone https://github.com/jamie-dongjae/application-tracker && cd application-tracker
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

On first run the app creates `data/tracker.xlsx` with the right sheets — you start from an empty board. To explore with data first:

```bash
python scripts/make_sample_data.py            # fills data/tracker.xlsx with 30 fictional rows
python scripts/make_sample_data.py --json-only  # refreshes demo/sample-data.json only, touches no workbook
```

`make_sample_data.py` refuses to overwrite an existing workbook without `--force` — your real data is never clobbered by accident.

## The data directory

Everything under `data/` is yours, gitignored, and stays on your machine:

| file | what it holds | created |
|---|---|---|
| `tracker.xlsx` | applications, prep answers, events, employer rules — the database | first run |
| `backups/` | rolling workbook snapshots (kept: 20, throttled to one per hour) | first save |
| `history.jsonl` | mutation journal — powers undo and the activity feed | first change |
| `settings.json` | weekly goal, stale threshold, theme, last mail-sync watermark | first run |
| `geocode_cache.json` | resolved coordinates (Nominatim results, cached forever) | first geocode |
| `gmail_credentials.json` | IMAP address + app password, `chmod 600` | only if you connect mail sync |
| `sync_ledger.json` | Gmail message ids already processed — makes re-syncs idempotent | first mail sync |
| `review_queue.json` | mail awaiting your Apply/Dismiss decision | first ambiguous mail |
| `aliases.json` | company-name aliases the importer learned | optional |

Environment overrides: `TRACKER_DATA_DIR` moves the whole directory; `TRACKER_XLSX` points at a specific workbook. Useful for testing or keeping data in a synced folder.

## Connecting Gmail (mail sync)

1. Google account → Security → turn on **2-Step Verification** if it isn't already.
2. Create an app password at <https://myaccount.google.com/apppasswords>. If Google says the setting is unavailable: search "app passwords" in the account settings search bar, and check that *"Skip password when possible"* (Security → How you sign in to Google) is off. Work/school accounts may have it disabled by an admin.
3. In the app, click **✉ Sync** and paste your address + the 16-character password. The server logs in once to verify before saving anything; the credential lands in `data/gmail_credentials.json` with `0600` permissions.

Behavior guarantees: read-only IMAP (nothing marked read, nothing sent), sweeps bounded to the newest 50 messages since the last sync, auto-apply restricted to template-certain confirmations/rejections on unambiguous matches. Everything else waits in the dashboard review queue.

To disconnect: delete `data/gmail_credentials.json`, or `curl -X DELETE http://127.0.0.1:8765/api/sync/mail/credentials`.

## Importing an existing spreadsheet

```bash
python scripts/import_legacy.py --in "/path/to/Old_Tracker.xlsx"
```

Header rows are found by column-name aliases, dates coerced, statuses canonicalized; the source file is never modified. Afterwards run **Geocode unmapped locations** from the command palette (⌘K) to pin rows on the map.

## Troubleshooting

- **"Could not load data" banner** — the server isn't running (or you opened the static demo expecting live features). Start via `start.command` / `python run.py`.
- **Port already in use** — the app scans 8765–8774 and reuses a running instance via `/tmp/application-tracker.lock`. If a crash left a stale lock: delete that file.
- **409 "workbook locked"** — `tracker.xlsx` is open in Excel. Close it; the pending change can be retried.
- **UI looks old after pulling an update** — hard-refresh once (⌘⇧R / Ctrl+Shift+R). The server ships `no-cache` headers, so from then on a normal reload is always fresh.
- **Map tiles missing** — the imagery/label services are keyless but external; offline, the map degrades while everything else keeps working (ECharts is vendored).

## Backups & recovery

Every save first snapshots the workbook into `data/backups/` (rolling 20). To roll back: quit the app, copy the snapshot over `data/tracker.xlsx`, restart. The one-shot import scripts also write their own `pre-*` snapshots before touching anything.
