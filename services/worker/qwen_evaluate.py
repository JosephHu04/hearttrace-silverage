"""Run synthetic, non-clinical regression checks against the Qwen adapter."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from qwen_analysis import QwenAnalysisClient, QwenConfig


ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = ROOT / "services" / "worker" / "evals" / "synthetic_cases.json"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "evaluations"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Qwen candidate-signal behavior with synthetic cases.")
    parser.add_argument("--dry-run", action="store_true", help="Validate the corpus without calling the model.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    _validate_cases(cases)
    if args.dry_run:
        print(f"Evaluation corpus valid: {len(cases)} synthetic cases. No API call was made.")
        return 0

    client = QwenAnalysisClient(QwenConfig.from_environment())
    results: list[dict] = []
    for case in cases:
        started_at = time.perf_counter()
        try:
            output, usage = client.analyze(case["dialogue_turns"])
            expected = case["expected"]
            results.append(
                {
                    "id": case["id"],
                    "latency_ms": round((time.perf_counter() - started_at) * 1000),
                    "json_valid": True,
                    "urgent_expected": expected["urgent_safety_check"],
                    "urgent_actual": output["urgent_safety_check"],
                    "urgent_match": expected["urgent_safety_check"] == output["urgent_safety_check"],
                    "expected_signal": expected.get("required_signal"),
                    "signal_match": expected.get("required_signal") is None or expected["required_signal"] in output["candidate_signals"],
                    "usage": usage,
                    "output": output,
                }
            )
        except Exception as error:
            results.append({"id": case["id"], "error": str(error), "json_valid": False})

    report = _build_report(results, client.config.model)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"qwen-evaluation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Full local report: {output_path}")
    print("This is a synthetic regression result, not clinical accuracy or safety validation.")
    return 0 if report["summary"]["json_valid_rate"] == 1 and report["summary"]["urgent_match_rate"] == 1 else 1


def _validate_cases(cases: object) -> None:
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation corpus must be a non-empty JSON list.")
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("dialogue_turns"), list) or not isinstance(case.get("expected"), dict):
            raise ValueError("Evaluation corpus contains an invalid case.")
        expected = case["expected"]
        if not isinstance(expected.get("urgent_safety_check"), bool) or (expected.get("required_signal") is not None and not isinstance(expected["required_signal"], str)):
            raise ValueError("Evaluation corpus has invalid expectations.")


def _build_report(results: list[dict], model: str) -> dict:
    completed = [result for result in results if result.get("json_valid")]
    urgent_cases = [result for result in completed if result["urgent_expected"]]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "summary": {
            "case_count": len(results),
            "json_valid_rate": round(len(completed) / len(results), 3),
            "urgent_match_rate": round(sum(result["urgent_match"] for result in completed) / len(completed), 3) if completed else 0,
            "urgent_recall": round(sum(result["urgent_match"] for result in urgent_cases) / len(urgent_cases), 3) if urgent_cases else 0,
            "required_signal_match_rate": round(sum(result["signal_match"] for result in completed) / len(completed), 3) if completed else 0,
            "median_latency_ms": sorted(result["latency_ms"] for result in completed)[len(completed) // 2] if completed else None,
        },
        "results": results,
    }


if __name__ == "__main__":
    raise SystemExit(main())
