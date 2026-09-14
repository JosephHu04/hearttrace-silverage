"""Run synthetic, non-clinical quality checks against the realtime companion."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.companion.client import CompanionClient
from app.services.companion.policy import plan_care_turn


ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = ROOT / "services" / "api" / "evals" / "synthetic_companion_cases.json"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "evaluations"
GLOBAL_FORBIDDEN_PHRASES = ("乖", "真棒", "老人家", "我完全理解", "抱抱您")
ALLOWED_CARE_MODES = {
    "natural_adult",
    "practical_help",
    "health_support",
    "emotional_support",
    "reminiscence",
    "repair_support",
    "repeat_support",
    "cognitive_support",
}


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    validate_cases(cases)
    return cases


def validate_cases(cases: object) -> None:
    if not isinstance(cases, list) or not cases:
        raise ValueError("Companion evaluation corpus must be a non-empty JSON list.")
    ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Every companion evaluation case must be an object.")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in ids:
            raise ValueError("Every companion evaluation case needs a unique non-empty id.")
        ids.add(case_id)
        if not isinstance(case.get("message"), str) or not case["message"].strip():
            raise ValueError(f"Case {case_id} needs a non-empty message.")
        history = case.get("history")
        if not isinstance(history, list) or any(
            not isinstance(item, dict)
            or item.get("role") not in {"user", "assistant"}
            or not isinstance(item.get("content"), str)
            for item in history
        ):
            raise ValueError(f"Case {case_id} has invalid history.")
        expected = case.get("expected")
        if not isinstance(expected, dict) or expected.get("care_mode") not in ALLOWED_CARE_MODES:
            raise ValueError(f"Case {case_id} has an invalid care mode.")
        if not isinstance(expected.get("max_chars"), int) or expected["max_chars"] < 20:
            raise ValueError(f"Case {case_id} needs a valid max_chars value.")
        if not isinstance(expected.get("max_questions"), int) or expected["max_questions"] < 0:
            raise ValueError(f"Case {case_id} needs a valid max_questions value.")
        if not isinstance(expected.get("wait_for_confirmation", False), bool):
            raise ValueError(f"Case {case_id} has an invalid wait_for_confirmation value.")
        for name in ("required_any", "forbidden_phrases"):
            values = expected.get(name)
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                raise ValueError(f"Case {case_id} has an invalid {name} list.")


def assess_reply(case: dict[str, Any], care_mode: str, reply: str) -> dict[str, bool]:
    expected = case["expected"]
    required_any = expected["required_any"]
    forbidden = [*GLOBAL_FORBIDDEN_PHRASES, *expected["forbidden_phrases"]]
    return {
        "care_mode": care_mode == expected["care_mode"],
        "not_empty": bool(reply.strip()),
        "concise": len(reply.strip()) <= expected["max_chars"],
        "single_question": reply.count("？") + reply.count("?") <= expected["max_questions"],
        "specific": not required_any or any(phrase in reply for phrase in required_any),
        "avoids_forbidden": not any(phrase in reply for phrase in forbidden),
        "spoken_plain_text": not any(marker in reply for marker in ("```", "\n#", "\n- ", "**")),
        "waits_for_confirmation": not expected.get("wait_for_confirmation", False)
        or any(
            phrase in reply
            for phrase in (
                "告诉我",
                "跟我说",
                "说一声",
                "看到了吗",
                "打开了吗",
                "现在看到",
                "现在在",
                "屏幕上",
                "还是",
                "了吗",
            )
        ),
    }


def _run_case(client: CompanionClient, case: dict[str, Any]) -> dict[str, Any]:
    history = list(case["history"])
    recent_users = [item["content"] for item in reversed(history) if item["role"] == "user"]
    recent_openings = [
        item["content"].splitlines()[0][:32]
        for item in reversed(history)
        if item["role"] == "assistant"
    ]
    plan = plan_care_turn(
        case["message"],
        turn_count=len(recent_users),
        recent_user_messages=recent_users,
        recent_openings=recent_openings,
    )
    history.append({"role": "user", "content": case["message"]})
    started = time.perf_counter()
    first_delta_ms: int | None = None
    if plan.direct_reply:
        model = "local-safety-router"
        reply = plan.direct_reply
        first_delta_ms = 0
    else:
        model, chunks = client.stream_reply(history, plan.context)
        parts: list[str] = []
        for chunk in chunks:
            if first_delta_ms is None:
                first_delta_ms = round((time.perf_counter() - started) * 1000)
            parts.append(chunk)
        reply = "".join(parts).strip()
    checks = assess_reply(case, plan.care_mode, reply)
    return {
        "id": case["id"],
        "model": model,
        "care_mode": plan.care_mode,
        "first_delta_ms": first_delta_ms,
        "total_ms": round((time.perf_counter() - started) * 1000),
        "passed": all(checks.values()),
        "checks": checks,
        "reply": reply,
    }


def build_report(results: list[dict[str, Any]], model: str) -> dict[str, Any]:
    completed = [item for item in results if "error" not in item]
    first_deltas = [
        item["first_delta_ms"]
        for item in results
        if item.get("first_delta_ms") is not None
    ]
    totals = [item["total_ms"] for item in results if "total_ms" in item]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "notice": "Synthetic conversational regression only; not clinical or real-user validation.",
        "summary": {
            "case_count": len(results),
            "completed_count": len(completed),
            "passed_count": sum(item["passed"] for item in results),
            "pass_rate": round(sum(item["passed"] for item in results) / len(results), 3),
            "quality_pass_rate": round(
                sum(item["passed"] for item in completed) / len(completed), 3
            )
            if completed
            else 0,
            "availability_rate": round(len(completed) / len(results), 3),
            "median_first_delta_ms": round(statistics.median(first_deltas)) if first_deltas else None,
            "median_total_ms": round(statistics.median(totals)) if totals else None,
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Qwen Flash elder-dialogue behavior.")
    parser.add_argument("--dry-run", action="store_true", help="Validate cases without an API call.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        choices=range(0, 3),
        help="Retries per synthetic case; this does not change production dialogue retries.",
    )
    args = parser.parse_args()
    cases = load_cases()
    if args.dry_run:
        print(f"Companion evaluation corpus valid: {len(cases)} synthetic cases. No API call was made.")
        return 0

    client = CompanionClient(get_settings())
    results: list[dict[str, Any]] = []
    for case in cases:
        for attempt in range(args.retries + 1):
            try:
                result = _run_case(client, case)
                result["attempts"] = attempt + 1
                results.append(result)
                break
            except Exception as error:
                if attempt == args.retries:
                    results.append(
                        {
                            "id": case["id"],
                            "passed": False,
                            "attempts": attempt + 1,
                            "error": f"{type(error).__name__}: {error}",
                        }
                    )
    report = build_report(results, get_settings().dashscope_companion_model)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = args.output_dir / f"companion-evaluation-{timestamp}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Full local report: {output_path}")
    print(report["notice"])
    return 0 if report["summary"]["pass_rate"] == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
