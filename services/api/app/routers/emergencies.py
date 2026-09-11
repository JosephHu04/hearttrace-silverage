from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.db.models import DeviceElderBinding, EmergencyEvent, User
from app.dependencies import DbSession, EmergencyActor, RiskStaff
from app.schemas import (
    EmergencyActionOut,
    EmergencyActionRequest,
    EmergencyActionResult,
    EmergencyCreateRequest,
    EmergencyCreateResult,
    EmergencyEventOut,
    EmergencyListOut,
    EmergencySource,
    EmergencyStatus,
)
from app.services.audit import add_audit_log
from app.services.emergencies import (
    EmergencyConflictError,
    EmergencyNotFoundError,
    apply_emergency_action,
    elder_name,
    list_emergencies,
)


router = APIRouter(tags=["emergency-events"])


def event_out(event: EmergencyEvent, name: str) -> EmergencyEventOut:
    return EmergencyEventOut(
        id=event.id,
        elder_id=event.elder_id,
        elder_name=name,
        trigger_actor_id=event.trigger_actor_id,
        source=event.source,
        status=event.status,
        note=event.note,
        acknowledged_by=event.acknowledged_by,
        acknowledged_at=event.acknowledged_at,
        resolved_by=event.resolved_by,
        resolved_at=event.resolved_at,
        version=event.version,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def resolve_elder_id(body: EmergencyCreateRequest, db: DbSession, actor: User) -> str:
    if actor.role == "elder":
        if body.source is not EmergencySource.elder_button:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="老人账号只能使用老人端求助入口")
        if body.elder_id is not None and body.elder_id != actor.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="不能替其他老人发起求助")
        return actor.id

    if body.source is not EmergencySource.device_button or body.elder_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="设备求助必须提供绑定老人和设备来源")
    binding = db.get(DeviceElderBinding, (actor.id, body.elder_id))
    if binding is None or not binding.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="设备未绑定该老人或绑定已停用")
    return body.elder_id


@router.post("/emergency/events", response_model=EmergencyCreateResult, status_code=status.HTTP_201_CREATED)
def create_emergency_event(
    body: EmergencyCreateRequest,
    db: DbSession,
    actor: EmergencyActor,
) -> EmergencyCreateResult:
    elder_id = resolve_elder_id(body, db, actor)
    existing = db.scalar(select(EmergencyEvent).where(EmergencyEvent.request_id == body.request_id))
    if existing is not None:
        if existing.elder_id != elder_id or existing.trigger_actor_id != actor.id or existing.source != body.source.value:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="幂等键已用于其他紧急事件")
        return EmergencyCreateResult(event=event_out(existing, elder_name(db, elder_id)), duplicate=True)

    elder = db.get(User, elder_id)
    if elder is None or elder.role != "elder" or not elder.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="老人账号不存在或已停用")
    event = EmergencyEvent(
        request_id=body.request_id,
        elder_id=elder_id,
        trigger_actor_id=actor.id,
        source=body.source.value,
        status=EmergencyStatus.open.value,
        note=(body.note or "").strip() or None,
    )
    db.add(event)
    db.flush()
    add_audit_log(
        db,
        actor_id=actor.id,
        action="emergency.created",
        target_type="emergency_event",
        target_id=event.id,
        metadata={"elderId": elder_id, "source": event.source},
    )
    db.commit()
    db.refresh(event)
    return EmergencyCreateResult(event=event_out(event, elder.display_name))


@router.get("/admin/emergency-events", response_model=EmergencyListOut)
def emergency_queue(
    db: DbSession,
    actor: RiskStaff,
    event_status: Optional[EmergencyStatus] = Query(default=None, alias="status"),
    elder_id: Optional[str] = Query(default=None, alias="elderId", max_length=64),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100, alias="perPage"),
) -> EmergencyListOut:
    rows, total = list_emergencies(
        db,
        event_status=event_status.value if event_status else None,
        elder_id=elder_id,
        page=page,
        per_page=per_page,
    )
    return EmergencyListOut(
        items=[event_out(event, name) for event, name in rows],
        page=page,
        per_page=per_page,
        total=total,
    )


@router.post("/admin/emergency-events/{event_id}/actions", response_model=EmergencyActionResult)
def emergency_action(
    event_id: str,
    body: EmergencyActionRequest,
    db: DbSession,
    actor: RiskStaff,
) -> EmergencyActionResult:
    try:
        outcome = apply_emergency_action(db, event_id=event_id, actor=actor, request=body)
    except EmergencyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="紧急事件不存在") from exc
    except EmergencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    action = outcome.action
    return EmergencyActionResult(
        event=event_out(outcome.event, elder_name(db, outcome.event.elder_id)),
        action=EmergencyActionOut.model_validate(action),
        duplicate=outcome.duplicate,
    )
