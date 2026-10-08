"""Account-bound signaling for family/elder audio calls.

Media is carried by LiveKit, never by this API. No audio is persisted.
"""

from __future__ import annotations

from datetime import timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.db.models import FamilyElderGrant, User, VoiceCallSession, utc_now
from app.dependencies import CurrentActor, DbSession
from app.services.audit import add_audit_log


router = APIRouter(prefix="/voice-calls", tags=["family-voice-calls"])
ACTIVE = ("ringing", "active")


class CallStart(BaseModel):
    target_id: str = Field(alias="targetId", min_length=1, max_length=64)


def require_participant(actor: User) -> None:
    if actor.role not in {"family", "elder"}:
        raise HTTPException(status_code=403, detail="仅老人和已授权家属可以通话")


def require_grant(db: DbSession, family_id: str, elder_id: str) -> None:
    grant = db.get(FamilyElderGrant, (family_id, elder_id))
    family = db.get(User, family_id)
    elder = db.get(User, elder_id)
    if (grant is None or not grant.is_active or grant.revoked_at is not None
            or "care_actions" not in grant.scopes or family is None or elder is None
            or not family.is_active or not elder.is_active
            or family.role != "family" or elder.role != "elder"):
        raise HTTPException(status_code=403, detail="双方没有有效的家属通话授权")


def ensure_configured() -> None:
    settings = get_settings()
    if not all((settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret)):
        raise HTTPException(status_code=503, detail="家人语音通话尚未配置，请联系管理员")


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def expire_stale(db: DbSession) -> None:
    now = utc_now()
    db.execute(
        update(VoiceCallSession)
        .where(VoiceCallSession.status == "ringing", VoiceCallSession.expires_at <= now)
        .values(status="missed", ended_at=now)
    )
    # A crashed or abandoned browser must not keep a person busy forever.
    db.execute(
        update(VoiceCallSession)
        .where(VoiceCallSession.status == "active", VoiceCallSession.answered_at <= now - timedelta(hours=2))
        .values(status="ended", ended_at=now)
    )
    db.commit()


def call_out(db: DbSession, call: VoiceCallSession, actor: User) -> dict[str, object]:
    counterpart = db.get(User, call.family_id if actor.role == "elder" else call.elder_id)
    return {
        "id": call.id,
        "status": call.status,
        "incoming": call.caller_id != actor.id,
        "counterpartId": counterpart.id if counterpart else "",
        "counterpartName": counterpart.display_name if counterpart else "家人",
        "createdAt": call.created_at,
        "expiresAt": call.expires_at,
        "answeredAt": call.answered_at,
    }


def get_call(db: DbSession, call_id: str, actor: User) -> VoiceCallSession:
    call = db.get(VoiceCallSession, call_id)
    if call is None or actor.id not in (call.elder_id, call.family_id):
        raise HTTPException(status_code=404, detail="通话不存在")
    return call


@router.get("/contacts")
def contacts(db: DbSession, actor: CurrentActor) -> dict[str, object]:
    require_participant(actor)
    if actor.role == "family":
        rows = db.execute(
            select(User, FamilyElderGrant).join(FamilyElderGrant, FamilyElderGrant.elder_id == User.id)
            .where(FamilyElderGrant.family_id == actor.id, FamilyElderGrant.is_active.is_(True),
                   FamilyElderGrant.revoked_at.is_(None), User.is_active.is_(True))
        ).all()
    else:
        rows = db.execute(
            select(User, FamilyElderGrant).join(FamilyElderGrant, FamilyElderGrant.family_id == User.id)
            .where(FamilyElderGrant.elder_id == actor.id, FamilyElderGrant.is_active.is_(True),
                   FamilyElderGrant.revoked_at.is_(None), User.is_active.is_(True))
        ).all()
    return {"items": [{"id": user.id, "name": user.display_name}
                      for user, grant in rows if "care_actions" in grant.scopes]}


@router.get("/current")
def current(db: DbSession, actor: CurrentActor) -> dict[str, object]:
    require_participant(actor)
    expire_stale(db)
    call = db.scalar(
        select(VoiceCallSession)
        .where(or_(VoiceCallSession.elder_id == actor.id, VoiceCallSession.family_id == actor.id),
               VoiceCallSession.status.in_(ACTIVE))
        .order_by(VoiceCallSession.created_at.desc()).limit(1)
    )
    if call is None:
        return {"call": None}
    try:
        require_grant(db, call.family_id, call.elder_id)
    except HTTPException:
        call.status = "ended"
        call.ended_at = utc_now()
        db.commit()
        return {"call": None}
    return {"call": call_out(db, call, actor)}


@router.post("")
def start_call(body: CallStart, db: DbSession, actor: CurrentActor) -> dict[str, object]:
    require_participant(actor)
    ensure_configured()
    target = db.get(User, body.target_id)
    if target is None or target.role == actor.role:
        raise HTTPException(status_code=404, detail="未找到可呼叫的家人")
    family_id = actor.id if actor.role == "family" else target.id
    elder_id = actor.id if actor.role == "elder" else target.id
    require_grant(db, family_id, elder_id)
    expire_stale(db)
    existing = db.scalar(
        select(VoiceCallSession).where(
            or_(VoiceCallSession.elder_id.in_((actor.id, target.id)),
                VoiceCallSession.family_id.in_((actor.id, target.id))),
            VoiceCallSession.status.in_(ACTIVE),
        ).limit(1)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="已有待接听或进行中的家人通话")
    call = VoiceCallSession(elder_id=elder_id, family_id=family_id, caller_id=actor.id,
                            status="ringing", expires_at=utc_now() + timedelta(seconds=45))
    db.add(call)
    try:
        db.flush()
        add_audit_log(db, actor_id=actor.id, action="voice_call.started", target_type="voice_call", target_id=call.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="对方正在通话，请稍后再试") from exc
    return {"call": call_out(db, call, actor)}


@router.post("/{call_id}/answer")
def answer_call(call_id: str, db: DbSession, actor: CurrentActor) -> dict[str, object]:
    require_participant(actor)
    expire_stale(db)
    call = get_call(db, call_id, actor)
    require_grant(db, call.family_id, call.elder_id)
    if call.caller_id == actor.id or call.status != "ringing" or aware(call.expires_at) <= utc_now():
        raise HTTPException(status_code=409, detail="此来电已无法接听")
    changed = db.execute(update(VoiceCallSession)
                         .where(VoiceCallSession.id == call.id, VoiceCallSession.status == "ringing")
                         .values(status="active", answered_at=utc_now()))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="来电状态已变化，请刷新后重试")
    add_audit_log(db, actor_id=actor.id, action="voice_call.answered", target_type="voice_call", target_id=call.id)
    db.commit()
    db.refresh(call)
    return {"call": call_out(db, call, actor)}


@router.post("/{call_id}/decline")
def decline_call(call_id: str, db: DbSession, actor: CurrentActor) -> dict[str, object]:
    require_participant(actor)
    call = get_call(db, call_id, actor)
    if call.caller_id == actor.id or call.status != "ringing":
        raise HTTPException(status_code=409, detail="此来电已无法拒接")
    changed = db.execute(update(VoiceCallSession)
                         .where(VoiceCallSession.id == call.id, VoiceCallSession.status == "ringing")
                         .values(status="declined", ended_at=utc_now()))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="来电状态已变化，请刷新后重试")
    add_audit_log(db, actor_id=actor.id, action="voice_call.declined", target_type="voice_call", target_id=call.id)
    db.commit()
    db.refresh(call)
    return {"call": call_out(db, call, actor)}


@router.post("/{call_id}/end")
def end_call(call_id: str, db: DbSession, actor: CurrentActor) -> dict[str, object]:
    require_participant(actor)
    call = get_call(db, call_id, actor)
    if call.status not in ACTIVE:
        return {"call": call_out(db, call, actor)}
    changed = db.execute(update(VoiceCallSession)
                         .where(VoiceCallSession.id == call.id, VoiceCallSession.status.in_(ACTIVE))
                         .values(status="ended", ended_at=utc_now()))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="通话状态已变化，请刷新后重试")
    add_audit_log(db, actor_id=actor.id, action="voice_call.ended", target_type="voice_call", target_id=call.id)
    db.commit()
    db.refresh(call)
    return {"call": call_out(db, call, actor)}


@router.post("/{call_id}/token")
def room_token(call_id: str, db: DbSession, actor: CurrentActor) -> dict[str, str]:
    require_participant(actor)
    ensure_configured()
    call = get_call(db, call_id, actor)
    require_grant(db, call.family_id, call.elder_id)
    if call.status != "active":
        raise HTTPException(status_code=409, detail="双方接通后才能加入语音房间")
    settings = get_settings()
    now = utc_now()
    token = jwt.encode({
        "iss": settings.livekit_api_key,
        "sub": f"{actor.role}-{actor.id}",
        "name": actor.display_name,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=2)).timestamp()),
        "video": {
            "roomJoin": True,
            "room": f"hearttrace-{call.id}",
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": False,
            "canPublishSources": ["microphone"],
        },
    }, settings.livekit_api_secret, algorithm="HS256")
    return {"url": settings.livekit_url, "token": token}
