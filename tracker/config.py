"""Runtime configuration. Everything lives under DATA_DIR (gitignored)."""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 8765

# last_sync is written by the sync importer only; SettingsPatch deliberately
# omits it so the UI settings endpoint can't clobber the watermark.
SETTINGS_DEFAULTS = {"weekly_goal": 5, "stale_days": 14, "theme": "dark", "last_sync": ""}


def data_dir() -> Path:
    d = Path(os.environ.get("TRACKER_DATA_DIR", REPO_ROOT / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def xlsx_path() -> Path:
    return Path(os.environ.get("TRACKER_XLSX", data_dir() / "tracker.xlsx"))


def geocode_cache_path() -> Path:
    return data_dir() / "geocode_cache.json"


def history_path() -> Path:
    return data_dir() / "history.jsonl"


def settings_path() -> Path:
    return data_dir() / "settings.json"


def aliases_path() -> Path:
    return data_dir() / "aliases.json"


def gmail_credentials_path() -> Path:
    return data_dir() / "gmail_credentials.json"


def review_queue_path() -> Path:
    return data_dir() / "review_queue.json"


def sync_ledger_path() -> Path:
    return data_dir() / "sync_ledger.json"


def load_settings() -> dict:
    out = dict(SETTINGS_DEFAULTS)
    try:
        out.update(json.loads(settings_path().read_text()))
    except (OSError, ValueError):
        pass
    return out


def save_settings(patch: dict) -> dict:
    settings = load_settings()
    settings.update({k: v for k, v in patch.items() if k in SETTINGS_DEFAULTS})
    settings_path().write_text(json.dumps(settings, indent=2))
    return settings
