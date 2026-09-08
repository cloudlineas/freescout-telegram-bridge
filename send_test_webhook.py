#!/usr/bin/env python3
"""
Post a correctly-signed fake FreeScout webhook at the bridge.

    python3 send_test_webhook.py                      # convo.created, valid signature
    python3 send_test_webhook.py --event convo.customer.reply.created
    python3 send_test_webhook.py --bad-signature      # expect HTTP 401
    python3 send_test_webhook.py --url http://localhost:8080/freescout

Reads FREESCOUT_WEBHOOK_SECRET from the environment or ./.env, so it signs with
exactly the same secret the bridge verifies with.
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request


def load_secret() -> str:
    secret = os.getenv("FREESCOUT_WEBHOOK_SECRET")
    if secret:
        return secret

    env_file = pathlib.Path(__file__).with_name(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("FREESCOUT_WEBHOOK_SECRET="):
                return line.split("=", 1)[1].strip()

    sys.exit("FREESCOUT_WEBHOOK_SECRET not set (env or ./.env)")


# Mirrors the shape of ApiWebhooks::formatEntity() for a Conversation.
PAYLOAD = {
    "id": 694,
    "number": 694,
    "threadsCount": 1,
    "type": "email",
    "folderId": 1,
    "status": "active",
    "state": "published",
    # The <script> tag is deliberate: it proves HTML escaping works.
    "subject": "Does this arrive? <script>alert(1)</script>",
    "preview": (
        "Hi! I cannot log in to my account. It says my password is wrong, "
        "but I am sure it is correct. Can you help? Thanks, Alex"
    ),
    "mailboxId": 1,
    "assignee": None,
    "createdBy": {
        "id": 42,
        "firstName": "Alex",
        "lastName": "Doe",
        "email": "alex@example.com",
    },
    "customer": {
        "id": 42,
        "firstName": "Alex",
        "lastName": "Doe",
        "email": "alex@example.com",
    },
    "cc": [],
    "bcc": [],
    "_embedded": {"threads": []},
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080/freescout")
    parser.add_argument("--event", default="convo.created")
    parser.add_argument("--bad-signature", action="store_true")
    args = parser.parse_args()

    secret = load_secret()

    # Sign the exact bytes we send -- this is what the bridge recomputes.
    body = json.dumps(PAYLOAD).encode()
    digest = hmac.new(secret.encode(), body, hashlib.sha1).digest()
    signature = base64.b64encode(digest).decode()
    if args.bad_signature:
        signature = "definitely-not-the-right-signature"

    request = urllib.request.Request(
        args.url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-FreeScout-Event": args.event,
            "X-FreeScout-Signature": signature,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            print(f"HTTP {response.status}: {response.read().decode()}")
            return 0
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode()}")
        # A 401 is the expected, correct outcome under --bad-signature.
        return 0 if args.bad_signature and exc.code == 401 else 1
    except urllib.error.URLError as exc:
        print(f"could not reach {args.url}: {exc.reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
