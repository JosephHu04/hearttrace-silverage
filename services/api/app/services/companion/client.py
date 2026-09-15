from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI

from app.core.config import Settings
from app.services.companion.prompt import ElderContext, build_elder_prompt, build_turn_guard


class CompanionClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = (
            OpenAI(
                api_key=settings.dashscope_api_key,
                base_url=settings.dashscope_base_url,
                timeout=max(3.0, settings.dashscope_companion_timeout_seconds),
                max_retries=0,
            )
            if settings.dashscope_api_key.strip()
            else None
        )

    @staticmethod
    def bounded_history(
        history: list[dict[str, str]], *, character_budget: int = 6000
    ) -> list[dict[str, str]]:
        selected: list[dict[str, str]] = []
        used = 0
        for item in reversed(history):
            content = item.get("content", "")
            if selected and used + len(content) > character_budget:
                break
            selected.append(item)
            used += len(content)
        selected.reverse()
        return selected

    def request_args(
        self, history: list[dict[str, str]], context: ElderContext
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("陪伴模型尚未配置。")
        bounded = self.bounded_history(
            history,
            character_budget=max(800, self.settings.companion_history_character_budget),
        )
        messages = [{"role": "system", "content": build_elder_prompt(context)}]
        if bounded:
            messages.extend(bounded[:-1])
            messages.append({"role": "system", "content": build_turn_guard(context)})
            messages.append(bounded[-1])
        return {
            "model": self.settings.dashscope_companion_model,
            "messages": messages,
            "temperature": 0.3,
            "top_p": 0.8,
            "max_tokens": max(80, self.settings.companion_max_tokens),
            "frequency_penalty": 0.18,
            "extra_body": {"enable_thinking": False, "preserve_thinking": False},
        }

    @staticmethod
    def _enforce_question_pause(content: str, context: ElderContext) -> str:
        """Guarantee a non-question turn after two recent assistant questions."""
        stripped = content.strip()
        if context.recent_question_count < 2:
            return stripped

        question_cue = re.compile(r"[？?]|(?:吗|呢|是否|有没有|怎么|为什么|哪(?:里|个|件)?)")
        sentences = re.findall(r"[^。！？!?]+[。！？!?]?", stripped)
        statements = [
            sentence.strip()
            for sentence in sentences
            if sentence.strip() and not question_cue.search(sentence)
        ]
        candidate = "".join(statements).strip()
        if context.care_mode == "health_support" and any(
            marker in candidate for marker in ("说明", "肯定是", "多半是")
        ):
            candidate = ""
        if candidate:
            return candidate

        fallbacks = {
            "practical_help": "这一步先停在当前页面，您慢慢看清屏幕上的文字或图标。",
            "health_support": "您刚说的情况我记下了。先按已有医嘱处理；如果明显加重，请联系医生。",
            "emotional_support": "这句话我听见了，您慢慢说。",
            "reminiscence": "这件事您慢慢讲，我听着。",
        }
        return fallbacks.get(context.care_mode, "嗯，您慢慢说，我听着。")

    def stream_reply(
        self, history: list[dict[str, str]], context: ElderContext
    ) -> tuple[str, Iterator[str]]:
        if self._client is None:
            raise RuntimeError("陪伴模型尚未配置。")
        request_args = self.request_args(history, context)
        retry_count = max(
            0,
            min(1, self.settings.dashscope_companion_connection_retries),
        )
        buffer_for_pause = context.recent_question_count >= 2

        def chunks() -> Iterator[str]:
            for attempt in range(retry_count + 1):
                emitted = False
                buffered: list[str] = []
                try:
                    response = self._client.chat.completions.create(
                        **request_args, stream=True
                    )
                    for part in response:
                        if not part.choices:
                            continue
                        text = part.choices[0].delta.content
                        if not text:
                            continue
                        if buffer_for_pause:
                            buffered.append(text)
                        else:
                            emitted = True
                            yield text
                    if buffer_for_pause:
                        yield self._enforce_question_pause(
                            "".join(buffered), context
                        )
                    return
                except APITimeoutError:
                    raise
                except (APIConnectionError, InternalServerError):
                    if emitted or attempt >= retry_count:
                        raise

        return self.settings.dashscope_companion_model, chunks()
