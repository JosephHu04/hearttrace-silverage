"""Authenticated one-utterance PCM relay for Qwen ASR Realtime.

The browser never receives the cloud API key. Audio and transcripts are not
persisted or logged; the existing HTTP ASR route remains the client fallback.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import secrets
import time
from urllib.parse import quote, urlparse

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.dependencies import resolve_actor_from_token


router = APIRouter(tags=["elder-speech"])
logger = logging.getLogger("uvicorn.error")


def _upstream_url() -> str:
    settings = get_settings()
    parsed = urlparse(settings.speech_dashscope_base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Invalid DashScope base URL")
    return f"wss://{parsed.netloc}/api-ws/v1/realtime?model={quote(settings.speech_asr_realtime_model)}"


def _event(event_type: str, **fields: object) -> str:
    return json.dumps({"event_id": f"event_{secrets.token_hex(8)}", "type": event_type, **fields})


async def _reject(websocket: WebSocket, *, code: int, message: str) -> None:
    await websocket.send_json({"type": "error", "message": message})
    await websocket.close(code=code)


@router.websocket("/realtime/speech")
async def realtime_speech(websocket: WebSocket) -> None:
    await websocket.accept()
    settings = get_settings()
    try:
        auth = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        token = auth.get("accessToken") if isinstance(auth, dict) and auth.get("type") == "authenticate" else None
        if not isinstance(token, str):
            await _reject(websocket, code=4401, message="请先完成语音认证")
            return
        with SessionLocal() as db:
            try:
                actor = resolve_actor_from_token(token, db)
            except HTTPException:
                await _reject(websocket, code=4401, message="登录已失效，请重新登录")
                return
            if actor.role != "elder":
                await _reject(websocket, code=4403, message="当前账号不能使用老人语音")
                return
        if settings.speech_provider != "dashscope" or not settings.speech_dashscope_api_key.strip():
            await _reject(websocket, code=4403, message="实时语音尚未配置")
            return

        trace_id = secrets.token_hex(6)
        started = time.perf_counter()
        audio_bytes = 0
        upstream = _upstream_url()
        async with connect(
            upstream,
            additional_headers={"Authorization": f"Bearer {settings.speech_dashscope_api_key}"},
            open_timeout=8,
            close_timeout=2,
            max_size=2_000_000,
        ) as cloud:
            created = json.loads(await asyncio.wait_for(cloud.recv(), timeout=8))
            if created.get("type") != "session.created":
                raise ValueError("ASR session creation failed")
            await cloud.send(_event("session.update", session={
                "input_audio_format": "pcm",
                "sample_rate": 16000,
                "turn_detection": None,
            }))
            updated = json.loads(await asyncio.wait_for(cloud.recv(), timeout=8))
            if updated.get("type") != "session.updated":
                raise ValueError("ASR session update failed")
            await websocket.send_json({"type": "ready"})

            while True:
                if time.perf_counter() - started > 65:
                    raise ValueError("ASR session exceeds duration limit")
                incoming = await asyncio.wait_for(websocket.receive(), timeout=60)
                if incoming.get("type") == "websocket.disconnect":
                    return
                chunk = incoming.get("bytes")
                if chunk is not None:
                    if not chunk or len(chunk) % 2 or len(chunk) > 65536:
                        raise ValueError("Invalid PCM chunk")
                    audio_bytes += len(chunk)
                    if audio_bytes > settings.speech_max_audio_bytes:
                        raise ValueError("Audio exceeds limit")
                    await cloud.send(_event("input_audio_buffer.append", audio=base64.b64encode(chunk).decode("ascii")))
                    continue
                try:
                    control = json.loads(incoming.get("text") or "")
                except json.JSONDecodeError as exc:
                    raise ValueError("Invalid ASR control") from exc
                if not isinstance(control, dict):
                    raise ValueError("Invalid ASR control")
                if control.get("type") == "cancel":
                    return
                if control.get("type") != "finish" or audio_bytes < 3200:
                    raise ValueError("No valid audio to transcribe")
                await cloud.send(_event("input_audio_buffer.commit"))
                await cloud.send(_event("session.finish"))
                transcript = ""
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    result = json.loads(await asyncio.wait_for(cloud.recv(), timeout=max(0.1, deadline - time.monotonic())))
                    kind = result.get("type")
                    if kind == "conversation.item.input_audio_transcription.completed":
                        transcript = str(result.get("transcript") or "").strip()
                    elif kind in {"error", "conversation.item.input_audio_transcription.failed"}:
                        raise ValueError("Upstream ASR error")
                    elif kind == "session.finished":
                        break
                logger.info("speech_latency trace=%s stage=asr_realtime outcome=ok elapsed_ms=%d audio_bytes=%d",
                            trace_id, round((time.perf_counter() - started) * 1000), audio_bytes)
                await websocket.send_json({"type": "final", "text": transcript})
                return
    except WebSocketDisconnect:
        return
    except (asyncio.TimeoutError, OSError, ValueError, WebSocketException) as exc:
        logger.warning("speech_latency stage=asr_realtime outcome=error kind=%s", type(exc).__name__)
        try:
            await _reject(websocket, code=1011, message="实时识别暂不可用，正在切换普通识别")
        except (RuntimeError, WebSocketDisconnect):
            pass
