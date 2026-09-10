"""Qwen adapter: candidate signals only, never a diagnosis or final risk level."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-plus"

SYSTEM_PROMPT = """你是“心迹银龄”的关怀分析助手。只分析已获得授权的对话摘要。
只返回一个 JSON 对象：
{"candidate_signals":["loneliness|sleep_change|low_mood|anxiety|cognitive_concern|crisis_language"],"urgent_safety_check":true,"recommended_next_step":"daily_care|invite_screening|human_follow_up|emergency_workflow","family_summary":"不超过80字、非诊断性的中文摘要","evidence_turn_indexes":[0]}
规则：不诊断疾病，不输出风险等级。仅明确自伤/自杀表达、明确生命安全危机或一键呼救时 urgent_safety_check 为 true。孤独、睡眠不好或一次低落不属于紧急事件。证据下标只能引用输入对话数组。紧急安全确认必须进入 emergency_workflow。"""


@dataclass(frozen=True)
class QwenConfig:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout_seconds: int = 30

    @classmethod
    def from_environment(cls) -> "QwenConfig":
        _load_optional_local_environment()
        api_key = os.getenv("DASHSCOPE_API_KEY", "")
        if not api_key or api_key == "replace-me":
            raise RuntimeError("请在本机环境变量 DASHSCOPE_API_KEY 中配置轮换后的百炼 API Key。")
        return cls(
            api_key=api_key,
            base_url=os.getenv("DASHSCOPE_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            model=os.getenv("DASHSCOPE_MODEL", DEFAULT_MODEL),
            timeout_seconds=int(os.getenv("DASHSCOPE_TIMEOUT_SECONDS", "30")),
        )


def _load_optional_local_environment() -> None:
    """Load only missing variables from the ignored repository-root .env.local file."""
    local_env = Path(__file__).resolve().parents[2] / ".env.local"
    if not local_env.is_file():
        return
    for raw_line in local_env.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


class QwenAnalysisClient:
    def __init__(self, config: QwenConfig) -> None:
        self.config = config

    def analyze(self, dialogue_turns: list[str]) -> tuple[dict[str, Any], dict[str, int]]:
        if not dialogue_turns:
            raise ValueError("至少需要一条已授权的对话内容。")
        indexed_turns = "\n".join(f"[{index}] {turn}" for index, turn in enumerate(dialogue_turns))
        body = {
            "model": self.config.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"以下是已授权的对话片段：\n{indexed_turns}"},
            ],
        }
        request = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"百炼调用失败（HTTP {error.code}）：{details}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"无法连接百炼服务：{error.reason}") from error

        try:
            content = payload["choices"][0]["message"]["content"]
            analysis = json.loads(_strip_code_fence(content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise RuntimeError("模型没有返回可解析的 JSON；请检查模型配置或提示词。") from error
        _validate_analysis(analysis, len(dialogue_turns))
        usage = payload.get("usage", {})
        return analysis, {"prompt_tokens": int(usage.get("prompt_tokens", 0)), "completion_tokens": int(usage.get("completion_tokens", 0))}


def _strip_code_fence(content: str) -> str:
    text = content.strip()
    return text.split("\n", 1)[1].rsplit("```", 1)[0].strip() if text.startswith("```") and text.endswith("```") else text


def _validate_analysis(analysis: Any, turn_count: int) -> None:
    if not isinstance(analysis, dict):
        raise RuntimeError("模型输出不是对象。")
    allowed_signals = {"loneliness", "sleep_change", "low_mood", "anxiety", "cognitive_concern", "crisis_language"}
    allowed_steps = {"daily_care", "invite_screening", "human_follow_up", "emergency_workflow"}
    signals, indexes = analysis.get("candidate_signals"), analysis.get("evidence_turn_indexes")
    if not isinstance(signals, list) or any(signal not in allowed_signals for signal in signals):
        raise RuntimeError("模型返回了不支持的候选信号。")
    if not isinstance(analysis.get("urgent_safety_check"), bool):
        raise RuntimeError("urgent_safety_check 必须是布尔值。")
    if analysis.get("recommended_next_step") not in allowed_steps:
        raise RuntimeError("模型返回了不支持的下一步建议。")
    if not isinstance(analysis.get("family_summary"), str) or len(analysis["family_summary"]) > 80:
        raise RuntimeError("family_summary 必须是不超过80字的字符串。")
    if not isinstance(indexes, list) or any(not isinstance(index, int) or index < 0 or index >= turn_count for index in indexes):
        raise RuntimeError("evidence_turn_indexes 不合法。")
    if analysis["urgent_safety_check"] and analysis["recommended_next_step"] != "emergency_workflow":
        raise RuntimeError("紧急安全确认必须进入 emergency_workflow。")
