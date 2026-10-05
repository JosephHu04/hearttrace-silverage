from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
import time
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import AuditLog, ConversationMessage, ConversationSession, User, utc_now
from app.db.session import SessionLocal
from app.dependencies import DbSession, ElderActor, resolve_actor_from_token
from app.schemas import ConversationMessageOut, ConversationPersona, ConversationSessionCreate, ConversationSessionOut
from app.services.companion.client import CompanionClient
from app.services.companion.live_info import build_live_info_result, detect_live_info_kind
from app.services.companion.policy import derive_memory_context, plan_care_turn
from app.services.companion.widgets import WidgetUnavailable, get_news, get_weather
from app.services.analysis_pipeline import queue_conversation_analysis


router = APIRouter(tags=["elder-conversations"])
settings = get_settings()
companion_client = CompanionClient(settings)
logger = logging.getLogger("uvicorn.error")


def _persona_fingerprint(persona: ConversationPersona) -> str:
    canonical = json.dumps(
        persona.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _session_out(session: ConversationSession) -> ConversationSessionOut:
    return ConversationSessionOut.model_validate(session)


@router.post(
    "/conversations/sessions",
    response_model=ConversationSessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation_session(
    body: ConversationSessionCreate,
    db: DbSession,
    elder: ElderActor,
) -> ConversationSessionOut:
    if any(len(item.strip()) < 2 or len(item.strip()) > 40 for item in body.persona.scenarios):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="人格适用场景每项需为 2 至 40 个字")
    session = ConversationSession(
        elder_id=elder.id,
        save_messages=body.save_messages,
        allow_analysis=body.allow_analysis,
    )
    db.add(session)
    db.flush()
    db.add(
        AuditLog(
            actor_id=elder.id,
            action="conversation.session_created",
            target_type="conversation_session",
            target_id=session.id,
            metadata_json={
                "saveMessages": body.save_messages,
                "allowAnalysis": body.allow_analysis,
                "persona": {"id": body.persona.id, "name": body.persona.name},
                "personaFingerprint": _persona_fingerprint(body.persona),
            },
        )
    )
    db.commit()
    db.refresh(session)
    return _session_out(session)


def _session_persona(
    db: DbSession, session_id: str, supplied: object,
) -> ConversationPersona:
    audit = db.scalar(
        select(AuditLog)
        .where(
            AuditLog.action == "conversation.session_created",
            AuditLog.target_type == "conversation_session",
            AuditLog.target_id == session_id,
        )
        .order_by(AuditLog.created_at.asc())
        .limit(1)
    )
    try:
        persona = ConversationPersona.model_validate(supplied or {})
    except ValueError:
        raise ValueError("人格配置格式不正确") from None
    fingerprint = (
        audit.metadata_json.get("personaFingerprint")
        if audit else _persona_fingerprint(ConversationPersona())
    )
    if not fingerprint:
        fingerprint = _persona_fingerprint(ConversationPersona())
    if fingerprint != _persona_fingerprint(persona):
        raise ValueError("人格配置与会话不一致")
    return persona


def _owned_session(db: DbSession, session_id: str, elder: User) -> ConversationSession:
    session = db.get(ConversationSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if session.elder_id != elder.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该会话")
    return session


@router.post("/conversations/sessions/{session_id}/revoke-analysis", response_model=ConversationSessionOut)
def revoke_analysis(session_id: str, db: DbSession, elder: ElderActor) -> ConversationSessionOut:
    session = _owned_session(db, session_id, elder)
    session.allow_analysis = False
    session.save_messages = False
    db.add(AuditLog(actor_id=elder.id, action="conversation.consent_revoked",
                    target_type="conversation_session", target_id=session.id,
                    metadata_json={"saveMessages": False, "allowAnalysis": False}))
    db.commit()
    return _session_out(session)


@router.get(
    "/conversations/sessions/{session_id}/messages",
    response_model=list[ConversationMessageOut],
)
def conversation_messages(
    session_id: str,
    db: DbSession,
    elder: ElderActor,
) -> list[ConversationMessageOut]:
    session = _owned_session(db, session_id, elder)
    db.add(
        AuditLog(
            actor_id=elder.id,
            action="conversation.messages_read",
            target_type="conversation_session",
            target_id=session.id,
            metadata_json={"messageStorage": session.save_messages},
        )
    )
    db.commit()
    if not session.save_messages:
        return []
    rows = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.session_id == session_id)
        .order_by(ConversationMessage.created_at.asc())
        .limit(100)
    ).all()
    return [ConversationMessageOut.model_validate(item) for item in rows]


@router.get("/elder/widgets/weather")
async def weather_widget(
    elder: ElderActor,
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
) -> dict[str, object]:
    del elder
    using_current_location = latitude is not None and longitude is not None
    latitude = settings.elder_default_latitude if latitude is None else latitude
    longitude = settings.elder_default_longitude if longitude is None else longitude
    try:
        return await asyncio.to_thread(
            get_weather,
            latitude,
            longitude,
            location="当前位置" if using_current_location else settings.elder_default_location,
        )
    except (ValueError, WidgetUnavailable) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/elder/widgets/news")
async def news_widget(elder: ElderActor, limit: int = Query(default=3, ge=1, le=8)) -> dict[str, object]:
    del elder
    try:
        return await asyncio.to_thread(get_news, limit)
    except WidgetUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


def _load_history(session_id: str, should_load: bool) -> list[dict[str, str]]:
    if not should_load:
        return []
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.created_at.desc())
                .limit(settings.companion_history_limit)
            ).all()
        )
    return [{"role": item.role, "content": item.content} for item in reversed(rows)]


def _load_memory_history(session_id: str, should_load: bool) -> list[dict[str, str]]:
    if not should_load:
        return []
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(ConversationMessage)
                .where(
                    ConversationMessage.session_id == session_id,
                    ConversationMessage.role == "user",
                )
                .order_by(ConversationMessage.created_at.desc())
                .limit(240)
            ).all()
        )
    return [{"role": "user", "content": item.content} for item in reversed(rows)]


def _persist_message(
    session_id: str,
    *,
    role: str,
    content: str,
    processing: str | None = None,
    model: str | None = None,
) -> None:
    with SessionLocal() as db:
        session = db.get(ConversationSession, session_id)
        if session is None:
            return
        session.last_active_at = utc_now()
        if session.save_messages:
            message = ConversationMessage(
                session_id=session_id,
                role=role,
                content=content,
                processing=processing,
                model=model,
            )
            db.add(message)
            db.flush()
            queue_conversation_analysis(db, session=session, source_message=message)
        db.commit()


def _next_chunk(iterator: Iterator[str]) -> tuple[bool, str]:
    try:
        return True, next(iterator)
    except StopIteration:
        return False, ""


def _fallback(care_mode: str) -> str:
    replies = {
        "emotional_support": "网络有点慢，但我在听。您愿意再多说一句吗？",
        "reminiscence": "刚才网络慢了一下，您说的这件事我记在这次谈话里。您接着说，我听着。",
        "practical_help": "刚才网络没有接稳。请告诉我您现在屏幕上看见什么，我们只做下一步。",
        "health_support": "刚才网络没有接稳。请再告诉我现在最明显的不舒服是什么，我接着听。",
    }
    return replies.get(care_mode, "刚才网络没有接稳。您的话我收到了，请再说一遍，我马上接着。")


async def _reject(websocket: WebSocket, *, code: int, message: str) -> None:
    await websocket.send_json({"type": "error", "message": message})
    await websocket.close(code=code)


@router.websocket("/realtime/conversation")
async def realtime_conversation(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        try:
            authentication = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        except (asyncio.TimeoutError, ValueError):
            await _reject(websocket, code=4401, message="请先完成会话认证")
            return
        if not isinstance(authentication, dict) or authentication.get("type") != "authenticate":
            await _reject(websocket, code=4401, message="第一条消息必须完成会话认证")
            return
        token = authentication.get("accessToken")
        session_id = authentication.get("sessionId")
        if not isinstance(token, str) or not isinstance(session_id, str):
            await _reject(websocket, code=4401, message="会话认证信息不完整")
            return

        with SessionLocal() as db:
            try:
                elder = resolve_actor_from_token(token, db)
            except HTTPException:
                await _reject(websocket, code=4401, message="访问令牌无效或已过期")
                return
            if elder.role != "elder":
                await _reject(websocket, code=4403, message="当前角色不是老人账号")
                return
            session = db.get(ConversationSession, session_id)
            if session is None or session.elder_id != elder.id:
                await _reject(websocket, code=4403, message="无权访问该会话")
                return
            save_messages = session.save_messages
            try:
                persona = _session_persona(db, session_id, authentication.get("persona"))
            except ValueError as exc:
                await _reject(websocket, code=4403, message=str(exc))
                return

        history = _load_history(session_id, save_messages)
        await websocket.send_json(
            {
                "type": "ready",
                "sessionId": session_id,
                "model": settings.dashscope_companion_model,
                "modelReady": bool(settings.dashscope_api_key.strip()),
                "messageStorage": save_messages,
                "persona": {"id": persona.id, "name": persona.name},
            }
        )

        while True:
            incoming = await websocket.receive_json()
            with SessionLocal() as db:
                try:
                    resolve_actor_from_token(token, db)
                except HTTPException:
                    await _reject(websocket, code=4401, message="登录已失效，请重新登录")
                    return
            if not isinstance(incoming, dict):
                await websocket.send_json({"type": "error", "message": "消息格式不正确"})
                continue
            if incoming.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if incoming.get("type") != "message":
                await websocket.send_json({"type": "error", "message": "不支持的消息类型"})
                continue
            message = incoming.get("text")
            if not isinstance(message, str) or not message.strip():
                await websocket.send_json({"type": "error", "message": "消息不能为空"})
                continue
            message = message.strip()
            if len(message) > 8000:
                await websocket.send_json({"type": "error", "message": "消息过长，请分几次发送"})
                continue

            raw_knowledge = incoming.get("knowledge", [])
            if not isinstance(raw_knowledge, list):
                raw_knowledge = []
            persona_knowledge = [
                item.strip() for item in raw_knowledge
                if isinstance(item, str) and 0 < len(item.strip()) <= 600
            ][:4]

            started = time.perf_counter()
            trace_id = secrets.token_hex(6)
            previous_users = [item["content"] for item in reversed(history) if item["role"] == "user"]
            openings = [item["content"].splitlines()[0][:32] for item in reversed(history) if item["role"] == "assistant"]
            memory_context = derive_memory_context(
                [*_load_memory_history(session_id, save_messages), {"role": "user", "content": message}], message
            ) if save_messages else None
            plan = plan_care_turn(
                message,
                turn_count=sum(1 for item in history if item["role"] == "user"),
                recent_user_messages=previous_users,
                recent_openings=openings,
                persona=persona.model_dump(mode="json"),
                memory_context=memory_context,
                persona_knowledge=persona_knowledge,
            )
            history.append({"role": "user", "content": message})
            history = history[-settings.companion_history_limit:]
            _persist_message(session_id, role="user", content=message, processing=plan.processing)
            preparation_ms = round((time.perf_counter() - started) * 1000)

            kind = None if plan.direct_reply else detect_live_info_kind(message)
            if kind:
                await websocket.send_json({"type": "progress", "kind": kind})
            live_info = await asyncio.to_thread(build_live_info_result, message, settings) if kind else None
            if live_info:
                await websocket.send_json({"type": "widget", **live_info.widget})

            reply_parts: list[str] = []
            first_delta_ms: int | None = None
            upstream_connect_ms: int | None = None
            failure_kind: str | None = None
            upstream_status: int | None = None
            model = "local-safety-router" if plan.direct_reply else "local-live-info" if live_info else settings.dashscope_companion_model
            try:
                if plan.direct_reply or live_info:
                    iterator: Iterator[str] = iter((plan.direct_reply or live_info.reply,))
                elif kind:
                    model = "local-live-info-unavailable"
                    iterator = iter(("实时信息暂时没有取到，请稍后再试。",))
                else:
                    model, iterator = await asyncio.to_thread(companion_client.stream_reply, history, plan.context)
                    upstream_connect_ms = round((time.perf_counter() - started) * 1000) - preparation_ms
                await websocket.send_json(
                    {
                        "type": "meta",
                        "model": model,
                        "scene": plan.scene,
                        "processing": plan.processing,
                        "familiarity": plan.familiarity,
                        "careMode": plan.care_mode,
                        "persona": {"id": persona.id, "name": persona.name},
                        "memoryContextCount": len(memory_context.memories) if memory_context else 0,
                    }
                )
                while True:
                    has_chunk, chunk = await asyncio.to_thread(_next_chunk, iterator)
                    if not has_chunk:
                        break
                    if first_delta_ms is None:
                        first_delta_ms = round((time.perf_counter() - started) * 1000)
                    reply_parts.append(chunk)
                    await websocket.send_json({"type": "delta", "text": chunk})
                reply = "".join(reply_parts).strip()
                if not reply:
                    raise RuntimeError("模型返回空回复")
            except (APIConnectionError, APITimeoutError, APIStatusError, RateLimitError, RuntimeError) as exc:
                failure_kind = type(exc).__name__
                upstream_status = getattr(exc, "status_code", None)
                logger.warning(
                    "companion_failure trace=%s kind=%s upstream_status=%s elapsed_ms=%d",
                    trace_id, failure_kind, upstream_status, round((time.perf_counter() - started) * 1000),
                )
                model_unconfigured = not settings.dashscope_api_key.strip()
                reply = (
                    "陪伴聊天模型尚未配置。请联系管理员完成配置后再试，紧急情况请直接使用呼救功能。"
                    if model_unconfigured else _fallback(plan.care_mode)
                )
                model = "local-model-unconfigured" if model_unconfigured else "local-network-fallback"
                first_delta_ms = round((time.perf_counter() - started) * 1000)
                await websocket.send_json({"type": "meta", "model": model, "processing": "model_unconfigured" if model_unconfigured else "network_fallback"})
                await websocket.send_json({"type": "delta", "text": reply})

            history.append({"role": "assistant", "content": reply})
            history = history[-settings.companion_history_limit:]
            _persist_message(session_id, role="assistant", content=reply, processing=plan.processing, model=model)
            total_ms = round((time.perf_counter() - started) * 1000)
            logger.info(
                "companion_latency trace=%s model=%s preparation_ms=%d upstream_connect_ms=%s "
                "first_delta_ms=%s total_ms=%d outcome=%s",
                trace_id, model, preparation_ms, upstream_connect_ms, first_delta_ms,
                total_ms, failure_kind or "ok",
            )
            await websocket.send_json(
                {
                    "type": "done",
                    "reply": reply,
                    "model": model,
                    "traceId": trace_id,
                    "preparationMs": preparation_ms,
                    "upstreamConnectMs": upstream_connect_ms,
                    "firstDeltaMs": first_delta_ms,
                    "totalMs": total_ms,
                }
            )
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("Unexpected realtime conversation failure")
        try:
            await websocket.send_json({"type": "error", "message": "会话暂时中断，请重新连接"})
        except Exception:
            pass
