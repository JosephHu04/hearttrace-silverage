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
    parser.add_argument(
        "--models",
        help="Comma-separated model IDs to compare with the same cases and prompt.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    _validate_cases(cases)
    requested_models = [item.strip() for item in (args.models or "").split(",") if item.strip()]
    if args.dry_run:
        comparison = f" Candidate models: {', '.join(requested_models)}." if requested_models else ""
        print(f"Evaluation corpus valid: {len(cases)} synthetic cases.{comparison} No API call was made.")
        return 0

    base_config = QwenConfig.from_environment()
    models = requested_models or [base_config.model]
    reports = [
        _evaluate_model(
            cases,
            QwenConfig(
                api_key=base_config.api_key,
                base_url=base_config.base_url,
                model=model,
                timeout_seconds=base_config.timeout_seconds,
            ),
        )
        for model in models
    ]
    comparison_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notice": "Synthetic regression only; not clinical accuracy or safety validation.",
        "models": reports,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"qwen-model-comparison-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    output_path.write_text(json.dumps(comparison_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({report["model"]: report["summary"] for report in reports}, ensure_ascii=False, indent=2))
    print(f"Full local report: {output_path}")
    print(comparison_report["notice"])
    return 0 if all(_passes_release_gate(report["summary"]) for report in reports) else 1


def _evaluate_model(cases: list[dict], config: QwenConfig) -> dict:
    client = QwenAnalysisClient(config)
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
                    "step_expected": expected["recommended_next_step"],
                    "step_actual": output["recommended_next_step"],
                    "step_match": expected["recommended_next_step"] == output["recommended_next_step"],
                    "usage": usage,
                    "output": output,
                }
            )
        except Exception as error:
            results.append({"id": case["id"], "error": str(error), "json_valid": False})
    return _build_report(results, client.config.model)


def _passes_release_gate(summary: dict) -> bool:
    return (
        summary["json_valid_rate"] == 1
        and summary["urgent_recall"] == 1
        and summary["urgent_precision"] == 1
        and summary["next_step_match_rate"] >= 0.9
        and summary["required_signal_recall"] >= 0.9
    )


def _validate_cases(cases: object) -> None:
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation corpus must be a non-empty JSON list.")
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("dialogue_turns"), list) or not isinstance(case.get("expected"), dict):
            raise ValueError("Evaluation corpus contains an invalid case.")
        expected = case["expected"]
        allowed_steps = {"daily_care", "invite_screening", "human_follow_up", "emergency_workflow"}
        if not isinstance(expected.get("urgent_safety_check"), bool) or (expected.get("required_signal") is not None and not isinstance(expected["required_signal"], str)) or expected.get("recommended_next_step") not in allowed_steps:
            raise ValueError("Evaluation corpus has invalid expectations.")


def _build_report(results: list[dict], model: str) -> dict:
    completed = [result for result in results if result.get("json_valid")]
    urgent_tp = sum(result["urgent_expected"] and result["urgent_actual"] for result in completed)
    urgent_fp = sum(not result["urgent_expected"] and result["urgent_actual"] for result in completed)
    urgent_fn = sum(result["urgent_expected"] and not result["urgent_actual"] for result in completed)
    urgent_precision = urgent_tp / (urgent_tp + urgent_fp) if urgent_tp + urgent_fp else 0
    urgent_recall = urgent_tp / (urgent_tp + urgent_fn) if urgent_tp + urgent_fn else 0
    urgent_f1 = 2 * urgent_precision * urgent_recall / (urgent_precision + urgent_recall) if urgent_precision + urgent_recall else 0
    signal_cases = [result for result in completed if result.get("expected_signal") is not None]
    latencies = sorted(result["latency_ms"] for result in completed)
    p95_index = max(0, round(0.95 * len(latencies) + 0.5) - 1) if latencies else 0
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "summary": {
            "case_count": len(results),
            "json_valid_rate": round(len(completed) / len(results), 3),
            "urgent_match_rate": round(sum(result["urgent_match"] for result in completed) / len(completed), 3) if completed else 0,
            "urgent_precision": round(urgent_precision, 3),
            "urgent_recall": round(urgent_recall, 3),
            "urgent_f1": round(urgent_f1, 3),
            "required_signal_match_rate": round(sum(result["signal_match"] for result in completed) / len(completed), 3) if completed else 0,
            "required_signal_recall": round(sum(result["signal_match"] for result in signal_cases) / len(signal_cases), 3) if signal_cases else 0,
            "next_step_match_rate": round(sum(result["step_match"] for result in completed) / len(completed), 3) if completed else 0,
            "median_latency_ms": latencies[len(latencies) // 2] if latencies else None,
            "p95_latency_ms": latencies[p95_index] if latencies else None,
            "total_prompt_tokens": sum(result.get("usage", {}).get("prompt_tokens", 0) for result in completed),
            "total_completion_tokens": sum(result.get("usage", {}).get("completion_tokens", 0) for result in completed),
        },
        "results": results,
    }


if __name__ == "__main__":
    raise SystemExit(main())
