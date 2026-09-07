"""
FreeScout -> Telegram webhook bridge.

FreeScout's API & Webhooks module POSTs a JSON conversation entity and signs it
with:

    X-FreeScout-Signature: base64(hmac_sha1(raw_body, md5(APP_KEY . "webhook_key")))
    X-FreeScout-Event:     e.g. convo.created

(see Modules/ApiWebhooks/Entities/Webhook.php::run/sign)

This service verifies that signature and forwards a short summary to Telegram.
It deliberately returns a non-2xx status when Telegram rejects the message, so
FreeScout records the failure in its webhook log instead of failing silently --
silent delivery failure is the exact problem this bridge exists to avoid.
"""

import base64
import hashlib
import hmac
import html
import logging
import os
import sys

import requests
from flask import Flask, jsonify, request

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("fs-telegram")


def _require(name):
    value = os.getenv(name)
    if not value:
        log.error("missing required env var %s", name)
        sys.exit(1)
    return value


TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _require("TELEGRAM_CHAT_ID")
WEBHOOK_SECRET = _require("FREESCOUT_WEBHOOK_SECRET")

# Leave on. The off switch exists only so a signature mismatch can be diagnosed
# on a dev machine without editing code.
VERIFY_SIGNATURE = os.getenv("VERIFY_SIGNATURE", "true").lower() != "false"

# Must stay https. Telegram's Bot API has no "open in system browser" parameter,
# and non-https schemes (x-safari-https://, intent://) are a dead end: the API
# accepts them but the iOS client strips them, leaving unclickable text.
# Whether a link opens in-app is purely a client-side setting.
# Unset means messages simply carry no "Open in FreeScout" link.
FREESCOUT_URL = os.getenv("FREESCOUT_URL", "").rstrip("/")

PREVIEW_CHARS = int(os.getenv("PREVIEW_CHARS", "300"))
TELEGRAM_TIMEOUT = float(os.getenv("TELEGRAM_TIMEOUT", "10"))

# Events that produce a Telegram message. Anything else is acknowledged with 200
# and dropped, so adding an event in the FreeScout UI can't wedge the webhook.
EVENTS = {
    e.strip()
    for e in os.getenv("EVENTS", "convo.created,convo.customer.reply.created").split(",")
    if e.strip()
}

# "1:Support,2:Sales" -> {1: "Support", 2: "Sales"}
MAILBOX_NAMES = {}
for pair in os.getenv("MAILBOX_NAMES", "").split(","):
    if ":" in pair:
        mailbox_id, _, name = pair.partition(":")
        try:
            MAILBOX_NAMES[int(mailbox_id.strip())] = name.strip()
        except ValueError:
            log.warning("ignoring malformed MAILBOX_NAMES entry %r", pair)

EVENT_TITLES = {
    "convo.created": "🎫 New ticket",
    "convo.customer.reply.created": "💬 Customer replied",
    "convo.agent.reply.created": "↩️ Agent replied",
    "convo.assigned": "👤 Assigned",
    "convo.note.created": "📝 Note added",
    "convo.status": "🔄 Status changed",
}

app = Flask(__name__)


def signature_ok(raw_body: bytes, provided: str) -> bool:
    digest = hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, provided or "")


def describe_sender(convo: dict) -> str:
    person = convo.get("customer") or convo.get("createdBy") or {}
    name = " ".join(
        part for part in (person.get("firstName"), person.get("lastName")) if part
    ).strip()
    email = person.get("email") or ""
    if name and email:
        return f"{name} <{email}>"
    return name or email or "unknown sender"


def build_message(event: str, convo: dict) -> str:
    """Telegram HTML. Every interpolated value is escaped."""
    esc = html.escape

    title = EVENT_TITLES.get(event, f"📨 {event}")
    number = convo.get("number") or convo.get("id")
    mailbox = MAILBOX_NAMES.get(convo.get("mailboxId"))

    header = f"<b>{esc(title)} #{esc(str(number))}</b>"
    if mailbox:
        header += f" · {esc(mailbox)}"

    lines = [header, f"<b>From:</b> {esc(describe_sender(convo))}"]

    subject = (convo.get("subject") or "").strip()
    if subject:
        lines.append(f"<b>Subject:</b> {esc(subject)}")

    preview = (convo.get("preview") or "").strip()
    if preview:
        if len(preview) > PREVIEW_CHARS:
            preview = preview[:PREVIEW_CHARS].rstrip() + "…"
        lines.append("")
        lines.append(f"<i>{esc(preview)}</i>")

    convo_id = convo.get("id")
    if convo_id and FREESCOUT_URL:
        url = f"{FREESCOUT_URL}/conversation/{convo_id}"
        lines.append("")
        lines.append(f'<a href="{esc(url)}">Open in FreeScout</a>')

    return "\n".join(lines)


def send_to_telegram(text: str) -> requests.Response:
    return requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=TELEGRAM_TIMEOUT,
    )


@app.get("/healthz")
def healthz():
    return jsonify(status="ok", events=sorted(EVENTS), verify_signature=VERIFY_SIGNATURE)


@app.post("/freescout")
def freescout_webhook():
    raw_body = request.get_data()
    event = request.headers.get("X-FreeScout-Event", "")

    if VERIFY_SIGNATURE and not signature_ok(
        raw_body, request.headers.get("X-FreeScout-Signature", "")
    ):
        log.warning("rejected webhook with bad signature (event=%s)", event)
        return jsonify(error="invalid signature"), 401

    if event not in EVENTS:
        log.info("ignoring event %s", event)
        return jsonify(status="ignored", event=event), 200

    convo = request.get_json(silent=True)
    if not isinstance(convo, dict):
        log.warning("event %s had a non-object JSON body", event)
        return jsonify(error="expected a JSON object"), 400

    text = build_message(event, convo)

    try:
        response = send_to_telegram(text)
    except requests.RequestException as exc:
        log.error("telegram request failed: %s", exc)
        return jsonify(error=f"telegram request failed: {exc}"), 502

    if not response.ok:
        # Surfaced to FreeScout's webhook log rather than swallowed.
        log.error("telegram returned %s: %s", response.status_code, response.text[:500])
        return jsonify(error="telegram rejected the message", detail=response.text[:500]), 502

    log.info("delivered %s for conversation %s", event, convo.get("id"))
    return jsonify(status="sent"), 200
