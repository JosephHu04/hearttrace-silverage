from __future__ import annotations

import asyncio
import base64
from io import BytesIO
from dataclasses import dataclass
from urllib.parse import urlparse
import wave

import httpx

from app.core.config import get_settings


class SpeechServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SynthesizedAudio:
    data: bytes
    sample_rate: int
    audio_format: str = "wav"


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
    if settings.speech_provider == "dashscope":
        # This is configuration readiness, not a paid live inference probe.
        configured = bool(settings.speech_dashscope_api_key.strip())
        return {"asr": configured, "tts": configured}
    if settings.speech_provider != "local":
        return {"asr": False, "tts": False}
    asr_ready, tts_ready = await asyncio.gather(
        _service_ready(f"{settings.funasr_url.rstrip('/')}/health"),
        _service_ready(f"{settings.fish_speech_url.rstrip('/')}/v1/health"),
    )
    return {"asr": asr_ready, "tts": tts_ready}


def _cloud_headers() -> dict[str, str]:
    api_key = get_settings().speech_dashscope_api_key.strip()
    if not api_key:
        raise SpeechServiceError("Speech API key is not configured")
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _wav_sample_rate(data: bytes) -> int:
    try:
        with wave.open(BytesIO(data), "rb") as wav:
            if wav.getnframes() == 0:
                raise SpeechServiceError("Empty WAV audio")
            return wav.getframerate()
    except (wave.Error, EOFError) as exc:
        raise SpeechServiceError("Invalid WAV audio") from exc


async def transcribe_with_dashscope(wav: bytes) -> str:
    settings = get_settings()
    _wav_sample_rate(wav)
    data_uri = "data:audio/wav;base64," + base64.b64encode(wav).decode("ascii")
    payload = {
        "model": settings.speech_asr_model,
        "messages": [{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": data_uri}}]}],
        "stream": False,
        "asr_options": {"enable_itn": False},
    }
    try:
        async with httpx.AsyncClient(timeout=settings.speech_request_timeout_seconds) as client:
            response = await client.post(
                f"{settings.speech_dashscope_base_url.rstrip('/')}/compatible-mode/v1/chat/completions",
                json=payload,
                headers=_cloud_headers(),
            )
            response.raise_for_status()
            result = response.json()
        transcript = result["choices"][0]["message"]["content"]
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise SpeechServiceError("DashScope ASR unavailable or invalid response") from exc
    if not isinstance(transcript, str):
        raise SpeechServiceError("DashScope ASR returned invalid text")
    return transcript.strip()


def _approved_audio_url(url: str) -> bool:
    parsed = urlparse(url)
    # DashScope returns a short-lived OSS URL. Never fetch an arbitrary URL
    # supplied through model output or a tampered API response.
    try:
        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname == "dashscope-result-bj.oss-cn-beijing.aliyuncs.com"
            and not parsed.username
            and not parsed.password
            and parsed.port in {None, 80, 443}
        )
    except ValueError:
        return False


async def synthesize_with_dashscope(text: str) -> SynthesizedAudio:
    settings = get_settings()
    payload = {
        "model": settings.speech_tts_model,
        "input": {
            "text": text,
            "voice": settings.speech_tts_voice,
            "format": "wav",
            "sample_rate": 24000,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=settings.speech_request_timeout_seconds, follow_redirects=False) as client:
            response = await client.post(
                f"{settings.speech_dashscope_base_url.rstrip('/')}/api/v1/services/audio/tts/SpeechSynthesizer",
                json=payload,
                headers=_cloud_headers(),
            )
            response.raise_for_status()
            result = response.json()
            audio_url = result["output"]["audio"]["url"]
            if not isinstance(audio_url, str) or not _approved_audio_url(audio_url):
                raise SpeechServiceError("DashScope TTS returned an untrusted audio URL")
            audio_response = await client.get(audio_url)
            audio_response.raise_for_status()
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise SpeechServiceError("DashScope TTS unavailable or invalid response") from exc
    if len(audio_response.content) > 32_000_000:
        raise SpeechServiceError("DashScope TTS returned oversized audio")
    return SynthesizedAudio(data=audio_response.content, sample_rate=_wav_sample_rate(audio_response.content))


async def transcribe_audio(wav: bytes) -> str:
    provider = get_settings().speech_provider
    if provider == "dashscope":
        return await transcribe_with_dashscope(wav)
    if provider == "local":
        return await transcribe_with_funasr(wav)
    raise SpeechServiceError("Unknown speech provider")


async def synthesize_audio(text: str) -> SynthesizedAudio:
    provider = get_settings().speech_provider
    if provider == "dashscope":
        return await synthesize_with_dashscope(text)
    if provider == "local":
        return await synthesize_with_fish_speech(text)
    raise SpeechServiceError("Unknown speech provider")


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
        # The API client waits for the complete response. Non-streaming mode
        # produces a standard WAV file that browsers can decode reliably.
        "streaming": False,
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
        with wave.open(BytesIO(response.content), "rb") as wav:
            if wav.getnframes() == 0:
                raise SpeechServiceError("Fish Speech returned empty WAV audio")
            sample_rate = wav.getframerate()
    except (wave.Error, EOFError) as exc:
        raise SpeechServiceError("Fish Speech returned invalid WAV audio") from exc
    return SynthesizedAudio(data=response.content, sample_rate=sample_rate)
