"""Gmail IMAP client for the in-app mail sync button. Stdlib only.

Auth is a Google app password (Account → Security → 2-Step Verification →
App passwords), stored locally with 0600 permissions. All auth lives in this
module so a future switch to OAuth touches one file. Fetching is strictly
read-only: the mailbox is selected readonly and bodies use BODY.PEEK, so
nothing is ever marked as read.

Gmail's X-GM-MSGID IMAP attribute, rendered as hex, equals the Gmail REST API
message id — which is what the sync ledger stores — so mail seen through this
client and mail seen through other Gmail channels dedup against each other.
"""
from __future__ import annotations

import email
import email.utils
import imaplib
import json
import os
import re
import socket
from datetime import date
from email.header import decode_header
from html.parser import HTMLParser

from .. import config

BODY_MAX_CHARS = 4096
ALL_MAIL = '"[Gmail]/All Mail"'


class MailboxError(Exception):
    code = "mailbox_error"


class NoCredentialsError(MailboxError):
    code = "no_credentials"


class MailAuthError(MailboxError):
    code = "auth_failed"


class MailNetworkError(MailboxError):
    code = "network"


# ---------- credentials ----------

def load_credentials() -> dict:
    try:
        creds = json.loads(config.gmail_credentials_path().read_text())
    except (OSError, ValueError):
        raise NoCredentialsError("no Gmail credentials configured")
    if not creds.get("email") or not creds.get("app_password"):
        raise NoCredentialsError("incomplete Gmail credentials")
    return creds


def save_credentials(email_addr: str, app_password: str) -> None:
    path = config.gmail_credentials_path()
    # Google renders app passwords as "xxxx xxxx xxxx xxxx" — spaces are noise.
    path.write_text(json.dumps({"email": email_addr.strip(),
                                "app_password": app_password.replace(" ", "")}))
    os.chmod(path, 0o600)


def delete_credentials() -> bool:
    path = config.gmail_credentials_path()
    if path.exists():
        path.unlink()
        return True
    return False


def credentials_status() -> dict:
    try:
        creds = load_credentials()
    except NoCredentialsError:
        return {"configured": False, "email": ""}
    addr = creds["email"]
    local, _, domain = addr.partition("@")
    masked = (local[0] + "···" if local else "···") + "@" + domain
    return {"configured": True, "email": masked}


# ---------- connection ----------

def _connect(email_addr: str, app_password: str) -> imaplib.IMAP4_SSL:
    try:
        conn = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    except (OSError, socket.error) as exc:
        raise MailNetworkError(f"could not reach imap.gmail.com: {exc}") from exc
    try:
        conn.login(email_addr, app_password)
    except imaplib.IMAP4.error as exc:
        raise MailAuthError(f"Gmail rejected the login: {exc}") from exc
    return conn


def verify_login(email_addr: str, app_password: str) -> None:
    conn = _connect(email_addr.strip(), app_password.replace(" ", ""))
    try:
        conn.logout()
    except imaplib.IMAP4.error:
        pass


# ---------- pure parsing (fixture-testable, no network) ----------

def gm_msgid_hex(msgid) -> str:
    """Gmail X-GM-MSGID (decimal) -> the Gmail REST/MCP message id (hex)."""
    return format(int(msgid), "x")


class _TextExtractor(HTMLParser):
    _SKIP = {"style", "script", "head"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth and data.strip():
            self.parts.append(data.strip())


def _html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
    return " ".join(extractor.parts)


def _decode_subject(raw) -> str:
    out = []
    for chunk, charset in decode_header(raw or ""):
        if isinstance(chunk, bytes):
            out.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(chunk)
    return "".join(out).strip()


def _extract_body(msg: email.message.Message) -> str:
    plain, html = "", ""
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html") or part.get("Content-Disposition", "").startswith("attachment"):
            continue
        try:
            payload = part.get_payload(decode=True)
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace") if payload else ""
        except Exception:
            continue
        if ctype == "text/plain" and not plain:
            plain = text
        elif ctype == "text/html" and not html:
            html = text
    body = plain or _html_to_text(html)
    return re.sub(r"[ \t]+", " ", body)[:BODY_MAX_CHARS]


def parse_message(raw: bytes, gm_msgid) -> dict:
    msg = email.message_from_bytes(raw)
    from_name, from_addr = email.utils.parseaddr(msg.get("From", ""))
    when = ""
    try:
        parsed = email.utils.parsedate_to_datetime(msg.get("Date", ""))
        if parsed:
            when = parsed.date().isoformat()
    except (TypeError, ValueError):
        pass
    return {
        "gmail_id": gm_msgid_hex(gm_msgid),
        "from_name": from_name,
        "from_addr": from_addr.lower(),
        "from_domain": from_addr.rsplit("@", 1)[-1].lower() if "@" in from_addr else "",
        "subject": _decode_subject(msg.get("Subject")),
        "date": when,
        "body": _extract_body(msg),
    }


_MSGID_RE = re.compile(rb"X-GM-MSGID\s+(\d+)")


def parse_fetch_response(data: list) -> list[tuple[int, bytes]]:
    """imaplib FETCH responses arrive as [(b'1 (X-GM-MSGID 123 BODY[] {n}', b'raw'), b')', ...];
    pair each metadata segment's X-GM-MSGID with its literal body."""
    out = []
    for item in data:
        if not isinstance(item, tuple) or len(item) < 2:
            continue
        m = _MSGID_RE.search(item[0])
        if m:
            out.append((int(m.group(1)), item[1]))
    return out


# ---------- fetching ----------

def fetch_messages(creds: dict, since: date, limit: int = 50) -> tuple[list[dict], list[str]]:
    """Return (messages, warnings). Read-only; newest `limit` messages since `since`."""
    warnings: list[str] = []
    conn = _connect(creds["email"], creds["app_password"])
    try:
        status, _ = conn.select(ALL_MAIL, readonly=True)
        if status != "OK":
            warnings.append("All Mail not exposed over IMAP — searching INBOX only")
            status, _ = conn.select("INBOX", readonly=True)
            if status != "OK":
                raise MailNetworkError("could not open any mailbox")
        try:
            status, data = conn.uid("SEARCH", None, f'SINCE {since.strftime("%d-%b-%Y")}')
        except imaplib.IMAP4.error as exc:
            raise MailNetworkError(f"search failed: {exc}") from exc
        uids = (data[0] or b"").split()
        if len(uids) > limit:
            warnings.append(f"{len(uids)} messages in window, processing newest {limit}")
            uids = uids[-limit:]
        if not uids:
            return [], warnings
        status, data = conn.uid("FETCH", b",".join(uids).decode(),
                                "(X-GM-MSGID BODY.PEEK[])")
        if status != "OK":
            raise MailNetworkError("fetch failed")
        return [parse_message(raw, msgid) for msgid, raw in parse_fetch_response(data)], warnings
    finally:
        try:
            conn.logout()
        except Exception:
            pass
