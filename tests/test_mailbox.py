"""Pure parsing functions of the IMAP client — no network."""
from tracker.services.mailbox import (
    BODY_MAX_CHARS, gm_msgid_hex, parse_fetch_response, parse_message,
)


def test_gm_msgid_hex_matches_gmail_rest_id():
    # X-GM-MSGID decimal -> Gmail REST/MCP hex id
    assert gm_msgid_hex(1877250402395428802) == format(1877250402395428802, "x")
    assert gm_msgid_hex("255") == "ff"


def _raw(headers: str, body: str) -> bytes:
    return (headers.strip() + "\r\n\r\n" + body).encode()


def test_parse_plain_message():
    raw = _raw("""
From: Acme Careers <no-reply@acme-jobs.example>
To: someone@example.com
Subject: Thank you for applying
Date: Thu, 25 Sep 2026 10:00:00 +0200
Content-Type: text/plain; charset=utf-8
""", "We received your application for Data Analyst.")
    msg = parse_message(raw, 255)
    assert msg["gmail_id"] == "ff"
    assert msg["from_addr"] == "no-reply@acme-jobs.example"
    assert msg["from_domain"] == "acme-jobs.example"
    assert msg["subject"] == "Thank you for applying"
    assert msg["date"] == "2026-09-25"
    assert "received your application" in msg["body"]


def test_parse_rfc2047_subject():
    raw = _raw("""
From: hr@beta.example
Subject: =?utf-8?B?QmVkYW5rdCB2b29yIGplIHNvbGxpY2l0YXRpZQ==?=
Date: Thu, 25 Sep 2026 10:00:00 +0200
Content-Type: text/plain
""", "hoi")
    assert parse_message(raw, 1)["subject"] == "Bedankt voor je sollicitatie"


def test_html_only_body_is_stripped():
    raw = _raw("""
From: hr@beta.example
Subject: Update
Date: Thu, 25 Sep 2026 10:00:00 +0200
Content-Type: text/html; charset=utf-8
""", "<html><head><style>p{color:red}</style></head><body><p>Unfortunately we will "
         "not proceed.</p></body></html>")
    body = parse_message(raw, 1)["body"]
    assert "Unfortunately we will not proceed." in body
    assert "color" not in body  # style content skipped


def test_multipart_prefers_plaintext_and_truncates():
    long = "x" * (BODY_MAX_CHARS + 500)
    raw = _raw("""
From: hr@beta.example
Subject: Update
Date: Thu, 25 Sep 2026 10:00:00 +0200
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="B"
""", f"""--B
Content-Type: text/plain; charset=utf-8

plain wins {long}
--B
Content-Type: text/html

<p>html loses</p>
--B--""")
    body = parse_message(raw, 1)["body"]
    assert body.startswith("plain wins")
    assert "html loses" not in body
    assert len(body) <= BODY_MAX_CHARS


def test_parse_fetch_response_pairs_msgid_with_literal():
    data = [
        (b"1 (X-GM-MSGID 255 BODY[] {10}", b"raw-one..."),
        b")",
        (b"2 (X-GM-MSGID 4096 BODY[] {10}", b"raw-two..."),
        b")",
    ]
    pairs = parse_fetch_response(data)
    assert pairs == [(255, b"raw-one..."), (4096, b"raw-two...")]
