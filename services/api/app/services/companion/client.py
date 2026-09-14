from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from openai import OpenAI

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

    def stream_reply(
        self, history: list[dict[str, str]], context: ElderContext
    ) -> tuple[str, Iterator[str]]:
        if self._client is None:
            raise RuntimeError("陪伴模型尚未配置。")
        response = self._client.chat.completions.create(
            **self.request_args(history, context), stream=True
        )

        def chunks() -> Iterator[str]:
            for part in response:
                if part.choices:
                    text = part.choices[0].delta.content
                    if text:
                        yield text

        return self.settings.dashscope_companion_model, chunks()
