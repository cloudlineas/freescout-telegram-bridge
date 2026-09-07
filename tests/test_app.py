import base64
import hashlib
import hmac
import json

import pytest
import requests

import app as bridge


@pytest.fixture
def client():
    bridge.app.config["TESTING"] = True
    with bridge.app.test_client() as c:
        yield c


@pytest.fixture
def telegram(monkeypatch):
    """Replace the Telegram call. No test ever needs a real token."""

    class Recorder:
        def __init__(self):
            self.calls = []
            self.status_code = 200
            self.text = "ok"
            self.raises = None

        @property
        def ok(self):
            return self.status_code < 400

        def __call__(self, text):
            self.calls.append(text)
            if self.raises:
                raise self.raises
            return self

        @property
        def last(self):
            return self.calls[-1]

    recorder = Recorder()
    monkeypatch.setattr(bridge, "send_to_telegram", recorder)
    return recorder


def sign(body: bytes, secret: str = "test-secret") -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha1).digest()).decode()


CONVO = {
    "id": 694,
    "number": 694,
    "subject": "Cannot log in",
    "preview": "I get an error when signing in.",
    "mailboxId": 1,
    "customer": {"firstName": "Alex", "lastName": "Doe", "email": "alex@example.com"},
}


def post(client, convo=CONVO, event="convo.created", signature=..., headers=None):
    body = json.dumps(convo).encode()
    hdrs = {"Content-Type": "application/json", "X-FreeScout-Event": event}
    if signature is ...:
        signature = sign(body)
    if signature is not None:
        hdrs["X-FreeScout-Signature"] = signature
    hdrs.update(headers or {})
    return client.post("/freescout", data=body, headers=hdrs)


# --- signature verification ------------------------------------------------


def test_valid_signature_is_accepted(client, telegram):
    assert post(client).status_code == 200
    assert len(telegram.calls) == 1


def test_wrong_signature_is_rejected_and_sends_nothing(client, telegram):
    response = post(client, signature="not-the-right-signature")
    assert response.status_code == 401
    assert telegram.calls == []


def test_signature_from_a_different_secret_is_rejected(client, telegram):
    body = json.dumps(CONVO).encode()
    response = post(client, signature=sign(body, "some-other-secret"))
    assert response.status_code == 401
    assert telegram.calls == []


def test_empty_signature_is_rejected(client, telegram):
    assert post(client, signature="").status_code == 401
    assert telegram.calls == []


def test_missing_signature_header_is_rejected(client, telegram):
    assert post(client, signature=None).status_code == 401
    assert telegram.calls == []


def test_signature_covers_the_body(client, telegram):
    """A signature valid for one body must not validate a different one."""
    stale = sign(json.dumps(CONVO).encode())
    tampered = dict(CONVO, subject="Tampered")
    assert post(client, convo=tampered, signature=stale).status_code == 401
    assert telegram.calls == []


def test_signature_check_can_be_disabled(client, telegram, monkeypatch):
    monkeypatch.setattr(bridge, "VERIFY_SIGNATURE", False)
    assert post(client, signature="garbage").status_code == 200


def test_signature_ok_helper_handles_none():
    assert bridge.signature_ok(b"{}", None) is False


# --- event filtering -------------------------------------------------------


@pytest.mark.parametrize("event", ["convo.created", "convo.customer.reply.created"])
def test_subscribed_events_are_delivered(client, telegram, event):
    assert post(client, event=event).status_code == 200
    assert len(telegram.calls) == 1


@pytest.mark.parametrize("event", ["convo.status", "convo.deleted", "", "nonsense"])
def test_unsubscribed_events_are_dropped_with_200(client, telegram, event):
    response = post(client, event=event)
    assert response.status_code == 200
    assert response.get_json()["status"] == "ignored"
    assert telegram.calls == []


def test_non_object_body_is_rejected(client, telegram):
    body = b"[1, 2, 3]"
    response = client.post(
        "/freescout",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-FreeScout-Event": "convo.created",
            "X-FreeScout-Signature": sign(body),
        },
    )
    assert response.status_code == 400
    assert telegram.calls == []


def test_healthz(client):
    body = client.get("/healthz").get_json()
    assert body["status"] == "ok"
    assert "convo.created" in body["events"]


# --- message building ------------------------------------------------------


def test_html_in_subject_is_escaped():
    text = bridge.build_message("convo.created", dict(CONVO, subject="<script>alert(1)</script>"))
    assert "<script>" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text


def test_html_in_sender_and_preview_is_escaped():
    text = bridge.build_message(
        "convo.created",
        dict(
            CONVO,
            preview="5 < 6 & 7 > 2",
            customer={"firstName": "<b>Bold</b>", "email": "a@example.com"},
        ),
    )
    assert "5 &lt; 6 &amp; 7 &gt; 2" in text
    assert "<b>Bold</b>" not in text


def test_known_event_gets_its_title():
    assert "🎫 New ticket" in bridge.build_message("convo.created", CONVO)


def test_unknown_event_falls_back_to_the_event_name():
    assert "convo.merged" in bridge.build_message("convo.merged", CONVO)


def test_mailbox_name_is_shown_when_mapped():
    assert "Support" in bridge.build_message("convo.created", CONVO)


def test_unmapped_mailbox_is_omitted():
    text = bridge.build_message("convo.created", dict(CONVO, mailboxId=99))
    assert "Support" not in text


def test_number_falls_back_to_id():
    convo = {k: v for k, v in CONVO.items() if k != "number"}
    assert "#694" in bridge.build_message("convo.created", convo)


# --- preview truncation ----------------------------------------------------


def test_long_preview_is_truncated(monkeypatch):
    monkeypatch.setattr(bridge, "PREVIEW_CHARS", 10)
    text = bridge.build_message("convo.created", dict(CONVO, preview="x" * 50))
    assert "x" * 10 + "…" in text
    assert "x" * 11 not in text


def test_short_preview_is_not_truncated(monkeypatch):
    monkeypatch.setattr(bridge, "PREVIEW_CHARS", 300)
    text = bridge.build_message("convo.created", dict(CONVO, preview="short"))
    assert "short" in text
    assert "…" not in text


def test_truncation_strips_trailing_whitespace(monkeypatch):
    monkeypatch.setattr(bridge, "PREVIEW_CHARS", 6)
    text = bridge.build_message("convo.created", dict(CONVO, preview="hello     world"))
    assert "<i>hello…</i>" in text


def test_missing_preview_is_omitted():
    convo = {k: v for k, v in CONVO.items() if k != "preview"}
    assert "<i>" not in bridge.build_message("convo.created", convo)


# --- sender fallbacks ------------------------------------------------------


def test_sender_uses_name_and_email():
    assert bridge.describe_sender(CONVO) == "Alex Doe <alex@example.com>"


def test_sender_falls_back_to_created_by_when_no_customer():
    convo = {"createdBy": {"firstName": "Sam", "email": "sam@example.com"}}
    assert bridge.describe_sender(convo) == "Sam <sam@example.com>"


def test_sender_falls_back_to_created_by_when_customer_is_null():
    convo = {"customer": None, "createdBy": {"firstName": "Sam"}}
    assert bridge.describe_sender(convo) == "Sam"


def test_sender_falls_back_to_email_only():
    assert bridge.describe_sender({"customer": {"email": "a@example.com"}}) == ("a@example.com")


def test_sender_handles_a_partial_name():
    assert bridge.describe_sender({"customer": {"lastName": "Doe"}}) == "Doe"


def test_sender_falls_back_to_unknown():
    assert bridge.describe_sender({}) == "unknown sender"
    assert bridge.describe_sender({"customer": {}}) == "unknown sender"


# --- the FreeScout link ----------------------------------------------------


def test_link_is_plain_https(monkeypatch):
    """Settled: no x-safari-https:// or intent:// -- the iOS client strips them."""
    monkeypatch.setattr(bridge, "FREESCOUT_URL", "https://helpdesk.example.com")
    text = bridge.build_message("convo.created", CONVO)
    assert '<a href="https://helpdesk.example.com/conversation/694">' in text


def test_link_is_omitted_when_no_base_url(monkeypatch):
    monkeypatch.setattr(bridge, "FREESCOUT_URL", "")
    assert "<a href=" not in bridge.build_message("convo.created", CONVO)


# --- failures must stay loud -----------------------------------------------


def test_telegram_rejection_returns_502(client, telegram):
    telegram.status_code = 400
    telegram.text = "Bad Request: chat not found"
    response = post(client)
    assert response.status_code == 502
    assert "chat not found" in response.get_json()["detail"]


def test_telegram_server_error_returns_502(client, telegram):
    telegram.status_code = 500
    assert post(client).status_code == 502


def test_telegram_network_failure_returns_502(client, telegram):
    telegram.raises = requests.ConnectionError("connection refused")
    response = post(client)
    assert response.status_code == 502
    assert "telegram request failed" in response.get_json()["error"]


def test_telegram_timeout_returns_502(client, telegram):
    telegram.raises = requests.Timeout("timed out")
    assert post(client).status_code == 502
