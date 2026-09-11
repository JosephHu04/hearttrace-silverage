from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import AuditLog, ConversationMessage, ConversationSession, User, utc_now
from app.db.session import SessionLocal
from app.dependencies import DbSession, ElderActor, resolve_actor_from_token
from app.schemas import ConversationMessageOut, ConversationSessionCreate, ConversationSessionOut
from app.services.companion.client import CompanionClient
from app.services.companion.live_info import build_live_info_result, detect_live_info_kind
from app.services.companion.policy import plan_care_turn
from app.services.companion.widgets import WidgetUnavailable, get_news, get_weather
from app.services.analysis_pipeline import queue_conversation_analysis


router = APIRouter(tags=["elder-conversations"])
settings = get_settings()
companion_client = CompanionClient(settings)
logger = logging.getLogger(__name__)


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
            },
        )
    )
    db.commit()
    db.refresh(session)
    return _session_out(session)


def _owned_session(db: DbSession, session_id: str, elder: User) -> ConversationSession:
    session = db.get(ConversationSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if session.elder_id != elder.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该会话")
    return session


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

        history = _load_history(session_id, save_messages)
        await websocket.send_json(
            {
                "type": "ready",
                "sessionId": session_id,
                "model": settings.dashscope_companion_model,
                "messageStorage": save_messages,
            }
        )

        while True:
            incoming = await websocket.receive_json()
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

            started = time.perf_counter()
            previous_users = [item["content"] for item in reversed(history) if item["role"] == "user"]
            openings = [item["content"].splitlines()[0][:32] for item in reversed(history) if item["role"] == "assistant"]
            plan = plan_care_turn(
                message,
                turn_count=sum(1 for item in history if item["role"] == "user"),
                recent_user_messages=previous_users,
                recent_openings=openings,
            )
            history.append({"role": "user", "content": message})
            history = history[-settings.companion_history_limit:]
            _persist_message(session_id, role="user", content=message, processing=plan.processing)

            kind = None if plan.direct_reply else detect_live_info_kind(message)
            if kind:
                await websocket.send_json({"type": "progress", "kind": kind})
            live_info = await asyncio.to_thread(build_live_info_result, message, settings) if kind else None
            if live_info:
                await websocket.send_json({"type": "widget", **live_info.widget})

            reply_parts: list[str] = []
            first_delta_ms: int | None = None
            model = "local-safety-router" if plan.direct_reply else "local-live-info" if live_info else settings.dashscope_companion_model
            try:
                if plan.direct_reply or live_info:
                    iterator: Iterator[str] = iter((plan.direct_reply or live_info.reply,))
                elif kind:
                    model = "local-live-info-unavailable"
                    iterator = iter(("实时信息暂时没有取到，请稍后再试。",))
                else:
                    model, iterator = await asyncio.to_thread(companion_client.stream_reply, history, plan.context)
                await websocket.send_json(
                    {
                        "type": "meta",
                        "model": model,
                        "scene": plan.scene,
                        "processing": plan.processing,
                        "familiarity": plan.familiarity,
                        "careMode": plan.care_mode,
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
                logger.warning("Companion generation degraded: %s", type(exc).__name__)
                reply = _fallback(plan.care_mode)
                model = "local-network-fallback"
                first_delta_ms = round((time.perf_counter() - started) * 1000)
                await websocket.send_json({"type": "meta", "model": model, "processing": "network_fallback"})
                await websocket.send_json({"type": "delta", "text": reply})

            history.append({"role": "assistant", "content": reply})
            history = history[-settings.companion_history_limit:]
            _persist_message(session_id, role="assistant", content=reply, processing=plan.processing, model=model)
            await websocket.send_json(
                {
                    "type": "done",
                    "reply": reply,
                    "model": model,
                    "firstDeltaMs": first_delta_ms,
                    "totalMs": round((time.perf_counter() - started) * 1000),
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
