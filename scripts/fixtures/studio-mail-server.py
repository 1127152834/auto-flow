"""Temporary real TLS SMTP/IMAP endpoints for the formal Studio UI smoke."""
from __future__ import annotations

import base64
import json
import signal
import sys
import time
from pathlib import Path

from test_b6_mail_transport_worker import LocalMailServer

root = Path(sys.argv[1])
status = Path(sys.argv[2])
smtp = LocalMailServer(root / "smtp", "smtp")
imap = LocalMailServer(root / "imap", "imap")
running = True


def shutdown(_signal: int, _frame: object) -> None:
    global running
    running = False


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)
try:
    while running:
        status.write_text(json.dumps({
            "smtpPort": smtp.port,
            "imapPort": imap.port,
            "messages": [base64.b64encode(message).decode("ascii") for message in smtp.messages],
            "smtpCommands": smtp.commands,
            "imapCommands": imap.commands,
            "imapFlags": imap.envelopes,
            "smtpDisconnected": smtp.disconnected.is_set(),
            "imapDisconnected": imap.disconnected.is_set(),
            "errors": [*smtp.errors, *imap.errors],
        }), encoding="utf-8")
        time.sleep(0.1)
finally:
    smtp.close()
    imap.close()
