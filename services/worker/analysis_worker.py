"""Consume consented conversation-analysis events from the database outbox."""

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
from app.services.analysis_pipeline import process_next_analysis_event  # noqa: E402
from qwen_analysis import QwenAnalysisClient, QwenConfig  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Process consented conversation-analysis outbox events.")
    parser.add_argument("--once", action="store_true", help="Process at most one available event, then exit.")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()

    config = QwenConfig.from_environment()
    analyzer = QwenAnalysisClient(config)
    while True:
        with SessionLocal() as db:
            outcome = process_next_analysis_event(db, analyzer=analyzer, model_version=config.model)
        if outcome is not None:
            print(
                json.dumps(
                    {
                        "eventId": outcome.event_id,
                        "status": outcome.status,
                        "analysisId": outcome.analysis_id,
                        "riskEventId": outcome.risk_event_id,
                        "error": outcome.error,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        if args.once:
            return 0 if outcome is None or outcome.status in {"processed", "skipped"} else 1
        if outcome is None:
            time.sleep(max(0.2, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
