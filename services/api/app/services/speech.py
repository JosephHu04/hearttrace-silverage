from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


class SpeechServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SynthesizedAudio:
    data: bytes
    sample_rate: int
    audio_format: str = "pcm_s16le"


def _headers() -> dict[str, str]:
    api_key = get_settings().speech_service_api_key.strip()
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


async def _service_ready(url: str) -> bool:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=min(settings.speech_request_timeout_seconds, 5.0)) as client:
            response = await client.get(url, headers=_headers())
        return response.is_success
    except httpx.HTTPError:
        return False


async def speech_health() -> dict[str, bool]:
    settings = get_settings()
    asr_ready, tts_ready = await asyncio.gather(
        _service_ready(f"{settings.funasr_url.rstrip('/')}/health"),
        _service_ready(f"{settings.fish_speech_url.rstrip('/')}/v1/health"),
    )
    return {"asr": asr_ready, "tts": tts_ready}


async def transcribe_with_funasr(wav: bytes) -> str:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=settings.speech_request_timeout_seconds) as client:
            response = await client.post(
                f"{settings.funasr_url.rstrip('/')}/transcribe",
                content=wav,
                headers={**_headers(), "Content-Type": "audio/wav"},
            )
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SpeechServiceError("FunASR service unavailable") from exc
    text = result.get("text")
    if not isinstance(text, str):
        raise SpeechServiceError("FunASR returned an invalid response")
    return text.strip()


async def synthesize_with_fish_speech(text: str) -> SynthesizedAudio:
    settings = get_settings()
    payload = {
        "text": text,
        "chunk_length": 100,
        "format": "wav",
        "reference_id": settings.fish_speech_reference_id,
        "use_memory_cache": "on",
        "streaming": True,
        "normalize": True,
        "max_new_tokens": 1024,
        "seed": 42,
        "top_p": 0.6,
        "repetition_penalty": 1.2,
        "temperature": 0.25,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.speech_request_timeout_seconds) as client:
            response = await client.post(
                f"{settings.fish_speech_url.rstrip('/')}/v1/tts",
                json=payload,
                headers=_headers(),
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SpeechServiceError("Fish Speech service unavailable") from exc
    if not response.content:
        raise SpeechServiceError("Fish Speech returned empty audio")
    try:
        sample_rate = int(response.headers.get("X-Audio-Sample-Rate", settings.fish_speech_sample_rate))
    except ValueError:
        sample_rate = settings.fish_speech_sample_rate
    return SynthesizedAudio(data=response.content, sample_rate=sample_rate)
