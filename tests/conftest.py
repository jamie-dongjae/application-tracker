import os
import tempfile

# Keep any module-level app creation away from the real data dir.
os.environ.setdefault("TRACKER_DATA_DIR", tempfile.mkdtemp(prefix="tracker-test-"))

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tracker.excel.store import ExcelStore
from tracker.main import create_app
from tracker.services.geocoder import Geocoder
from tracker.services.history import History

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def store(tmp_path):
    return ExcelStore(tmp_path / "tracker.xlsx")


@pytest.fixture
def geocoder(tmp_path):
    g = Geocoder(tmp_path / "geocode_cache.json")
    g._cache = {
        "utrecht, netherlands": {"lat": 52.09083, "lng": 5.12222,
                                 "display_name": "Utrecht, Netherlands", "ts": 0},
    }
    return g


@pytest.fixture
def client(tmp_path, store, geocoder):
    app = create_app(store=store,
                     history=History(tmp_path / "history.jsonl"),
                     geocoder=geocoder)
    return TestClient(app)


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text()
