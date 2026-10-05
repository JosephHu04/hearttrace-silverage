from __future__ import annotations

import logging
import secrets
import time

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.dependencies import ElderActor
from app.services.speech import SpeechServiceError, speech_health, synthesize_audio, transcribe_audio


router = APIRouter(prefix="/speech", tags=["elder-speech"])
logger = logging.getLogger("uvicorn.error")


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=800)


@router.get("/health")
async def get_speech_health(_: ElderActor) -> dict[str, bool | str]:
    result = await speech_health()
    provider = get_settings().speech_provider
    return {**result, "provider": provider, "realtimeAsr": provider == "dashscope" and result["asr"]}


@router.post("/transcribe")
async def transcribe(request: Request, _: ElderActor) -> dict[str, str]:
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "audio/wav":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="只接受 WAV 语音")
    wav = await request.body()
    settings = get_settings()
    if not wav:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="语音内容为空")
    if len(wav) > settings.speech_max_audio_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="单次语音过长")
    started = time.perf_counter()
    trace_id = secrets.token_hex(6)
    try:
        text = await transcribe_audio(wav)
    except SpeechServiceError as exc:
        logger.warning("speech_latency trace=%s stage=asr outcome=error kind=%s elapsed_ms=%d",
                       trace_id, type(exc.__cause__ or exc).__name__, round((time.perf_counter() - started) * 1000))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="语音识别服务暂时不可用") from exc
    logger.info("speech_latency trace=%s stage=asr outcome=ok elapsed_ms=%d audio_bytes=%d",
                trace_id, round((time.perf_counter() - started) * 1000), len(wav))
    return {"text": text}


@router.post("/synthesize")
async def synthesize(payload: SynthesisRequest, _: ElderActor) -> Response:
    settings = get_settings()
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="播报文字不能为空")
    if len(text) > settings.speech_max_tts_characters:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="单次播报文字过长")
    started = time.perf_counter()
    trace_id = secrets.token_hex(6)
    try:
        audio = await synthesize_audio(text)
    except SpeechServiceError as exc:
        logger.warning("speech_latency trace=%s stage=tts outcome=error kind=%s elapsed_ms=%d",
                       trace_id, type(exc.__cause__ or exc).__name__, round((time.perf_counter() - started) * 1000))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="语音合成服务暂时不可用") from exc
    logger.info("speech_latency trace=%s stage=tts outcome=ok elapsed_ms=%d text_chars=%d audio_bytes=%d",
                trace_id, round((time.perf_counter() - started) * 1000), len(text), len(audio.data))
    return Response(
        content=audio.data,
        media_type="audio/wav",
        headers={
            "Cache-Control": "no-store",
            "X-Audio-Format": audio.audio_format,
            "X-Audio-Sample-Rate": str(audio.sample_rate),
        },
    )
