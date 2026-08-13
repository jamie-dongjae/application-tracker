"""Mutation journal: powers undo and the status-transition analytics.

Every create/update/delete is appended to a JSONL file and kept on an
in-memory undo stack. Undo applies the inverse through the store.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

UNDO_DEPTH = 50


class History:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._undo: list[dict] = []
        self._entries: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open() as fh:
                self._entries = [json.loads(line) for line in fh if line.strip()]
        except (OSError, ValueError):
            self._entries = []

    def record(self, action: str, entity: str, entity_id, before, after, label: str = "",
               undoable: bool = True) -> dict:
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "entity": entity,
            "id": entity_id,
            "before": before,
            "after": after,
            "label": label,
        }
        with self._lock:
            self._entries.append(entry)
            if undoable:
                self._undo.append(entry)
                del self._undo[:-UNDO_DEPTH]
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a") as fh:
                    fh.write(json.dumps(entry, default=str) + "\n")
            except OSError:
                pass
        return entry

    def pop_undoable(self) -> dict | None:
        with self._lock:
            return self._undo.pop() if self._undo else None

    def push_back(self, entry: dict) -> None:
        """Re-stack an entry whose undo failed (e.g. workbook locked)."""
        with self._lock:
            self._undo.append(entry)

    def recent(self, n: int = 100) -> list[dict]:
        with self._lock:
            return list(self._entries[-n:])[::-1]

    def transitions(self) -> list[dict]:
        """Status changes only — feeds time-in-stage analytics."""
        with self._lock:
            out = []
            for e in self._entries:
                if e["entity"] != "application" or e["action"] != "update":
                    continue
                before, after = e.get("before") or {}, e.get("after") or {}
                if before.get("status") != after.get("status"):
                    out.append({
                        "ts": e["ts"],
                        "id": e["id"],
                        "from": before.get("status"),
                        "to": after.get("status"),
                    })
            return out
