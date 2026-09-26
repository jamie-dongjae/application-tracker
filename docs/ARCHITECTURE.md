# Architecture

A local-first FastAPI app whose database is an Excel workbook, with a vanilla-JS
frontend (no build step) and an optional read-only Gmail sync. Five runtime
dependencies: `fastapi`, `uvicorn`, `openpyxl`, `httpx`, `selectolax`.

## The store (tracker/excel/)

`ExcelStore` is the single owner of `data/tracker.xlsx`. Records live in memory
as lists of dicts; **every mutation rewrites the data sheets in full** from a
fresh styled template (`schema.init_workbook()`) and saves atomically
(tmp file + `os.replace`), after snapshotting a rolling backup. Consequences:

- Adding columns or sheets is just a schema change — the next save rewrites the
  file in the new layout. Older workbook versions upgrade in place on load
  (`schema_version` in the hidden Meta sheet; v2 → v3 → v4 all automatic).
- External edits made directly in Excel are picked up via an mtime/size
  signature check before reads. Writes while Excel holds the file open are
  refused (the `~$` owner sentinel) and surface as HTTP 409.
- Never run an older checkout against a newer workbook: its `_save()` would
  silently drop columns it doesn't know about.

Sheets: **Applications** (26 columns), **Interview Prep**, **Events**
(per-application timeline), **Employers** (per-company rules), hidden **Meta**.

## The v4 categorization ↔ kanban status sync

Applications carry two representations: the simple kanban `status`
(Wishlist/Applied/Interview/Offer/Accepted/Declined/Rejected/Withdrawn) and the
v4 fields (`track`, `stage_reached`, `current_state`, `outcome`, `closed_by`).
Two pure functions in `tracker/excel/schema.py` keep them consistent, applied
inside the store so every write path is covered:

- `derive_status(record)` — v4 fields → status (first-match rule table).
- `apply_status_forward(record, new_status)` — a board drag patches the v4
  fields; `stage_reached` is monotonic and never lowered.

The forward map round-trips through the derive table, so the representations
cannot drift. Field normalization (canonical `source` vocabulary, work-type
casing) also happens in the store's `_clean`, in `tracker/importers/normalize.py`.

## Sync packets — the integration point

External tools integrate by POSTing a **sync packet** to
`POST /api/import/sync` (`dry_run` defaults to true):

```json
{"packet_version": 1, "source": "my-tool", "generated_at": "2026-09-26T12:00:00",
 "records": [{
   "company": "Acme", "title": "Data Analyst",
   "match": {"title_contains": ["dataanalyst"]},
   "confidence": "review",
   "fields": {"date_applied": "2026-09-20", "source": "LinkedIn"},
   "patch": {"stage_reached": "confirmed"},
   "note": "appended to notes if absent",
   "events": [{"date": "2026-09-20", "event": "confirmed", "note": "…", "provenance": "gmail:<id>"}],
   "provenance": ["gmail:<id>"]}]}
```

Semantics (implemented in `tracker/importers/sync_packet.py`):

- **Upsert on (company, title)** through a conservative matcher
  (`tracker/importers/matching.py`): exact title → `title_contains` keywords →
  single-candidate token overlap. Ambiguity skips the record — never guesses.
- **Idempotency, twice over**: message ids from `provenance` land in
  `data/sync_ledger.json` (fully-absorbed records too), and events dedup by
  `(date, event, note-prefix)` plus id-in-notes. Re-POSTing a packet is a no-op.
- `stage_reached` merges monotonically; non-empty incoming values win
  elsewhere; notes append-if-absent. Every applied change is an undoable
  history entry (`POST /api/undo` reverses one at a time).
- On apply, `generated_at` becomes the `last_sync` watermark (in
  `settings.json`, exposed via `/api/health`, deliberately not writable through
  the settings endpoint).

The built-in mail sync (`tracker/services/mailbox.py` — stdlib IMAP, strictly
read-only; `tracker/importers/mail_rules.py` — deterministic EN/NL classifier)
is just one producer of these packets. Gmail's `X-GM-MSGID` rendered as hex
equals the Gmail REST message id, so any Gmail-derived producer shares the same
ledger. Ambiguous mail goes to `data/review_queue.json`, resolved through
`POST /api/sync/review/{id}/apply|dismiss` (a dismiss ledgers the id so the
mail never re-queues).

## Frontend (static/)

Plain ES modules, loaded straight from the server (which sends `no-cache` so
updates apply on any reload). `state.js` is a tiny store with pub/sub;
`loadAll()` fetches in two tiers — applications and settings are required,
everything else (prep, history, employers, review queue) degrades to empty
defaults so a partial backend never blanks the UI. Views render into fixed
sections; the Insights dashboard bridges CSS design tokens into ECharts via
`views/insights/theme.js:chartTokens()` (read at init, so theme flips restyle
charts). Design tokens live at the top of `static/css/app.css` — liquid-glass
material tiers, specular edge tokens, and the rule that `backdrop-filter`
belongs on containers only (cards are gradient pseudo-glass; ~180 blurring
cards would melt the GPU).

## The static demo (demo/)

GitHub Pages serves the real frontend with `demo/shim.js` monkey-patching
`fetch`: every `/api/*` call is answered from `demo/sample-data.json` in
memory. The mail sync is a scripted simulation. `demo/index.html` is
**generated** from `static/index.html` by `scripts/build_demo.py` (run in the
Pages workflow), so the demo can't drift from the app again. Sample data comes
from `scripts/make_sample_data.py --json-only` — fictional companies, seeded
RNG, authored in v4 terms with the status derived by the real store code.
