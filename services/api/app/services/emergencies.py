from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models import EmergencyAction, EmergencyEvent, User, utc_now
from app.schemas import EmergencyActionRequest
from app.services.audit import add_audit_log


class EmergencyNotFoundError(Exception):
    pass


class EmergencyConflictError(Exception):
    pass


@dataclass
class EmergencyActionOutcome:
    event: EmergencyEvent
    action: EmergencyAction
    duplicate: bool


TRANSITIONS: dict[str, dict[str, str]] = {
    "acknowledge": {"open": "acknowledged"},
    "resolve": {"open": "resolved", "acknowledged": "resolved"},
    "cancel": {"open": "cancelled", "acknowledged": "cancelled"},
    "reopen": {"resolved": "open", "cancelled": "open"},
}

NOTE_REQUIRED = {"resolve", "cancel", "reopen"}


def get_emergency(db: Session, event_id: str) -> EmergencyEvent:
    event = db.get(EmergencyEvent, event_id)
    if event is None:
        raise EmergencyNotFoundError
    return event


def elder_name(db: Session, elder_id: str) -> str:
    name = db.scalar(select(User.display_name).where(User.id == elder_id))
    if name is None:
        raise EmergencyNotFoundError
    return name


def list_emergencies(
    db: Session,
    *,
    event_status: Optional[str],
    elder_id: Optional[str],
    page: int,
    per_page: int,
) -> tuple[list[tuple[EmergencyEvent, str]], int]:
    filters = []
    if event_status is not None:
        filters.append(EmergencyEvent.status == event_status)
    if elder_id is not None:
        filters.append(EmergencyEvent.elder_id == elder_id)
    total = db.scalar(select(func.count()).select_from(EmergencyEvent).where(*filters)) or 0
    statement = (
        select(EmergencyEvent, User.display_name)
        .join(User, User.id == EmergencyEvent.elder_id)
        .where(*filters)
        .order_by(EmergencyEvent.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return list(db.execute(statement).all()), total


def apply_emergency_action(
    db: Session,
    *,
    event_id: str,
    actor: User,
    request: EmergencyActionRequest,
) -> EmergencyActionOutcome:
    existing = db.scalar(select(EmergencyAction).where(EmergencyAction.request_id == request.request_id))
    if existing is not None:
        if existing.emergency_event_id != event_id or existing.action != request.action.value:
            raise EmergencyConflictError("幂等键已用于其他紧急事件操作")
        return EmergencyActionOutcome(event=get_emergency(db, event_id), action=existing, duplicate=True)

    event = get_emergency(db, event_id)
    if event.version != request.expected_version:
        raise EmergencyConflictError(f"事件已更新，当前版本为 {event.version}")

    action_name = request.action.value
    next_status = TRANSITIONS.get(action_name, {}).get(event.status)
    if next_status is None:
        raise EmergencyConflictError(f"不能从 {event.status} 执行 {action_name}")
    note = (request.note or "").strip()
    if action_name in NOTE_REQUIRED and not note:
        raise EmergencyConflictError("该操作必须填写处置说明")

    now = utc_now()
    previous_status = event.status
    next_version = event.version + 1
    values: dict[str, object] = {"status": next_status, "version": next_version, "updated_at": now}
    if action_name == "acknowledge":
        values.update({"acknowledged_by": actor.id, "acknowledged_at": now})
    elif action_name in {"resolve", "cancel"}:
        values.update({"resolved_by": actor.id, "resolved_at": now})
    elif action_name == "reopen":
        values.update({"acknowledged_by": None, "acknowledged_at": None, "resolved_by": None, "resolved_at": None})

    result = db.execute(
        update(EmergencyEvent)
        .where(EmergencyEvent.id == event.id, EmergencyEvent.version == request.expected_version)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise EmergencyConflictError("事件已被其他工作人员更新，请刷新后重试")

    action = EmergencyAction(
        request_id=request.request_id,
        emergency_event_id=event.id,
        actor_id=actor.id,
        action=action_name,
        note=note or None,
        from_status=previous_status,
        to_status=next_status,
        event_version=next_version,
    )
    db.add(action)
    add_audit_log(
        db,
        actor_id=actor.id,
        action=f"emergency.{action_name}",
        target_type="emergency_event",
        target_id=event.id,
        metadata={"fromStatus": previous_status, "toStatus": next_status, "eventVersion": next_version},
    )
    db.commit()
    db.refresh(action)
    db.refresh(event)
    return EmergencyActionOutcome(event=event, action=action, duplicate=False)
