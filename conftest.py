"""app.py reads its config at import time and exits if the required vars are
missing, so they have to exist before the import happens."""

import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "12345")
os.environ.setdefault("FREESCOUT_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("FREESCOUT_URL", "https://helpdesk.example.com")
os.environ.setdefault("MAILBOX_NAMES", "1:Support,2:Sales")
