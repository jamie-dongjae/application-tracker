"""Mail sync endpoints: credentials, one-click sync, review queue. IMAP mocked."""
import json

import pytest

from tracker import config
from tracker.services import mailbox


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKER_DATA_DIR", str(tmp_path))


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setattr(mailbox, "load_credentials",
                        lambda: {"email": "test@example.com", "app_password": "x" * 16})


def _mock_fetch(messages, warnings=None):
    def fetch(creds, since, limit=50):
        return messages, warnings or []
    return fetch


CONFIRM_MSG = {"gmail_id": "aa11", "from_name": "Acme Corp Careers",
               "from_addr": "no-reply@acmecorp.example", "from_domain": "acmecorp.example",
               "subject": "Thanks for applying", "date": "2026-09-25",
               "body": "We received your application for Data Analyst."}
INVITE_MSG = {"gmail_id": "bb22", "from_name": "Acme Corp Careers",
              "from_addr": "no-reply@acmecorp.example", "from_domain": "acmecorp.example",
              "subject": "Interview invitation", "date": "2026-09-25",
              "body": "We would like to schedule an interview next week."}


def test_no_credentials_is_428(client):
    assert client.post("/api/sync/mail").status_code == 428


def test_sync_applies_and_queues(client, creds, monkeypatch):
    client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Analyst"})
    monkeypatch.setattr(mailbox, "fetch_messages", _mock_fetch([CONFIRM_MSG, INVITE_MSG]))
    resp = client.post("/api/sync/mail").json()
    assert resp["fetched"] == 2
    assert resp["applied"]["updated"] == 1     # confirmation auto-applied
    assert resp["queued"] == 1                 # invite queued for review

    app = client.get("/api/applications").json()["applications"][0]
    assert app["stage_reached"] == "confirmed"
    items = client.get("/api/sync/review").json()["items"]
    assert len(items) == 1 and items[0]["id"] == "bb22"
    ledger = json.loads(config.sync_ledger_path().read_text())
    assert "aa11" in ledger["gmail_ids"]       # applied -> ledgered
    assert client.get("/api/health").json()["last_sync"] is not None


def test_resync_is_idempotent(client, creds, monkeypatch):
    client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Analyst"})
    monkeypatch.setattr(mailbox, "fetch_messages", _mock_fetch([CONFIRM_MSG, INVITE_MSG]))
    client.post("/api/sync/mail")
    resp = client.post("/api/sync/mail").json()
    assert resp["already_known"] == 2          # ledger id + pending-queue id
    assert resp["applied"]["updated"] == 0 and resp["queued"] == 0
    assert len(client.get("/api/sync/review").json()["items"]) == 1  # not duplicated


def test_review_apply_updates_app_and_keeps_watermark(client, creds, monkeypatch):
    client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Analyst"})
    monkeypatch.setattr(mailbox, "fetch_messages", _mock_fetch([INVITE_MSG]))
    client.post("/api/sync/mail")
    watermark = client.get("/api/health").json()["last_sync"]

    item = client.get("/api/sync/review").json()["items"][0]
    # a human upgraded the guess before applying
    item["proposed"]["match"] = {"id": 1}
    item["proposed"]["patch"] = {"stage_reached": "recruiter_screen", "current_state": "scheduling"}
    queue = json.loads(config.review_queue_path().read_text())
    queue[0] = {**queue[0], "proposed": item["proposed"]}
    config.review_queue_path().write_text(json.dumps(queue))

    resp = client.post(f"/api/sync/review/{item['id']}/apply")
    assert resp.status_code == 200
    app = client.get("/api/applications").json()["applications"][0]
    assert app["status"] == "Interview" and app["current_state"] == "scheduling"
    assert client.get("/api/health").json()["last_sync"] == watermark  # not rewound
    assert client.get("/api/sync/review").json()["items"] == []
    # second apply -> 409
    assert client.post(f"/api/sync/review/{item['id']}/apply").status_code == 409


def test_dismiss_ledgers_and_blocks_requeue(client, creds, monkeypatch):
    client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Analyst"})
    monkeypatch.setattr(mailbox, "fetch_messages", _mock_fetch([INVITE_MSG]))
    client.post("/api/sync/mail")
    item_id = client.get("/api/sync/review").json()["items"][0]["id"]
    assert client.post(f"/api/sync/review/{item_id}/dismiss").status_code == 200
    ledger = json.loads(config.sync_ledger_path().read_text())
    assert item_id in ledger["gmail_ids"]
    resp = client.post("/api/sync/mail").json()
    assert resp["queued"] == 0 and not client.get("/api/sync/review").json()["items"]
    assert client.post("/api/sync/review/nope/dismiss").status_code == 404


def test_credentials_endpoints(client, monkeypatch):
    assert client.get("/api/sync/mail/credentials").json() == {"configured": False, "email": ""}

    def bad_login(email, pw):
        raise mailbox.MailAuthError("bad password")
    monkeypatch.setattr(mailbox, "verify_login", bad_login)
    resp = client.post("/api/sync/mail/credentials",
                       json={"email": "t@example.com", "app_password": "wrongwrong"})
    assert resp.status_code == 401
    assert not config.gmail_credentials_path().exists()  # nothing written on failure

    monkeypatch.setattr(mailbox, "verify_login", lambda e, p: None)
    resp = client.post("/api/sync/mail/credentials",
                       json={"email": "t@example.com", "app_password": "abcd efgh ijkl mnop"})
    assert resp.status_code == 200
    saved = json.loads(config.gmail_credentials_path().read_text())
    assert saved["app_password"] == "abcdefghijklmnop"  # spaces stripped

    status = client.get("/api/sync/mail/credentials").json()
    assert status["configured"] is True
    assert "app_password" not in status and status["email"].startswith("t···@")

    assert client.delete("/api/sync/mail/credentials").json()["deleted"] is True
    assert client.get("/api/sync/mail/credentials").json()["configured"] is False
