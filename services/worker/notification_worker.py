"""A durable notification worker using the in-app delivery adapter."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
os.chdir(ROOT / "services" / "api")

from app.db.session import SessionLocal  # noqa: E402
from app.services.notifications import (  # noqa: E402
    InAppNotificationAdapter,
    process_next_notification_event,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Process notification delivery outbox events.")
    parser.add_argument("--once", action="store_true", help="Process at most one available event, then exit.")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    adapter = InAppNotificationAdapter()

    while True:
        with SessionLocal() as db:
            outcome = process_next_notification_event(db, adapter=adapter)
        if outcome is not None:
            print(
                json.dumps(
                    {
                        "eventId": outcome.event_id,
                        "notificationId": outcome.notification_id,
                        "status": outcome.status,
                        "error": outcome.error,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        if args.once:
            return 0 if outcome is None or outcome.status == "processed" else 1
        if outcome is None:
            time.sleep(max(0.2, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
