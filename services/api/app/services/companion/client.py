from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from openai import OpenAI

from app.core.config import Settings
from app.services.companion.prompt import ElderContext, build_elder_prompt


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
        return {
            "model": self.settings.dashscope_companion_model,
            "messages": [
                {"role": "system", "content": build_elder_prompt(context)},
                *self.bounded_history(history),
            ],
            "temperature": 0.42,
            "top_p": 0.82,
            "max_tokens": 220,
            "frequency_penalty": 0.18,
            "extra_body": {"enable_thinking": False},
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
