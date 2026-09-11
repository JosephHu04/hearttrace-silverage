from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models import RiskAction, RiskEvent, RiskEvidence, User, utc_now
from app.schemas import RiskActionRequest
from app.services.analysis_pipeline import publish_confirmed_analysis_summary
from app.services.audit import add_audit_log


class RiskNotFoundError(Exception):
    pass


class RiskConflictError(Exception):
    pass


@dataclass
class ActionOutcome:
    event: RiskEvent
    action: RiskAction
    duplicate: bool


TRANSITIONS: dict[str, dict[str, str]] = {
    "claim": {"new": "assigned"},
    "begin_review": {"assigned": "reviewing"},
    "request_action": {"reviewing": "action_required"},
    "escalate": {"reviewing": "escalated", "action_required": "escalated"},
    "resolve": {"reviewing": "resolved", "action_required": "resolved", "escalated": "resolved"},
    "mark_false_positive": {"reviewing": "false_positive"},
    "close": {"resolved": "closed", "false_positive": "closed"},
    "reopen": {"closed": "reviewing"},
}

NOTE_REQUIRED = {"request_action", "escalate", "resolve", "mark_false_positive", "reopen"}


def list_risks(
    db: Session,
    *,
    level: Optional[str],
    event_status: Optional[str],
    page: int,
    per_page: int,
) -> tuple[list[tuple[RiskEvent, str]], int]:
    filters = []
    if level is not None:
        filters.append(RiskEvent.level == level)
    if event_status is not None:
        filters.append(RiskEvent.status == event_status)

    total = db.scalar(select(func.count()).select_from(RiskEvent).where(*filters)) or 0
    statement = (
        select(RiskEvent, User.display_name)
        .join(User, User.id == RiskEvent.elder_id)
        .where(*filters)
        .order_by(RiskEvent.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return list(db.execute(statement).all()), total


def get_risk(db: Session, event_id: str) -> RiskEvent:
    event = db.get(RiskEvent, event_id)
    if event is None:
        raise RiskNotFoundError
    return event


def get_risk_parts(db: Session, event: RiskEvent) -> tuple[str, list[RiskEvidence], list[RiskAction]]:
    elder_name = db.scalar(select(User.display_name).where(User.id == event.elder_id))
    if elder_name is None:
        raise RiskNotFoundError
    evidence = list(
        db.scalars(
            select(RiskEvidence)
            .where(RiskEvidence.risk_event_id == event.id)
            .order_by(RiskEvidence.recorded_at)
        )
    )
    actions = list(
        db.scalars(
            select(RiskAction)
            .where(RiskAction.risk_event_id == event.id)
            .order_by(RiskAction.created_at)
        )
    )
    return elder_name, evidence, actions


def apply_action(
    db: Session,
    *,
    event_id: str,
    actor: User,
    request: RiskActionRequest,
) -> ActionOutcome:
    existing = db.scalar(select(RiskAction).where(RiskAction.request_id == request.request_id))
    if existing is not None:
        if existing.risk_event_id != event_id:
            raise RiskConflictError("幂等键已用于其他事件")
        return ActionOutcome(event=get_risk(db, event_id), action=existing, duplicate=True)

    event = get_risk(db, event_id)
    if event.version != request.expected_version:
        raise RiskConflictError(f"事件已更新，当前版本为 {event.version}")

    action_name = request.action.value
    next_status = TRANSITIONS.get(action_name, {}).get(event.status)
    if next_status is None:
        raise RiskConflictError(f"不能从 {event.status} 执行 {action_name}")
    if action_name in NOTE_REQUIRED and not (request.note or "").strip():
        raise RiskConflictError("该操作必须填写复核说明")
    if action_name == "begin_review" and event.assignee_id not in {None, actor.id}:
        raise RiskConflictError("该事件已由其他工作人员认领")

    previous_status = event.status
    next_version = event.version + 1
    values: dict[str, object] = {
        "status": next_status,
        "version": next_version,
        "updated_at": utc_now(),
    }
    if action_name in {"claim", "reopen"}:
        values["assignee_id"] = actor.id

    update_result = db.execute(
        update(RiskEvent)
        .where(RiskEvent.id == event.id, RiskEvent.version == request.expected_version)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if update_result.rowcount != 1:
        db.rollback()
        raise RiskConflictError("事件已被其他工作人员更新，请刷新后重试")

    action = RiskAction(
        request_id=request.request_id,
        risk_event_id=event.id,
        actor_id=actor.id,
        action=action_name,
        note=(request.note or "").strip() or None,
        from_status=previous_status,
        to_status=next_status,
        event_version=next_version,
    )
    db.add(action)
    add_audit_log(
        db,
        actor_id=actor.id,
        action=f"risk.{action_name}",
        target_type="risk_event",
        target_id=event.id,
        metadata={"fromStatus": previous_status, "toStatus": next_status, "eventVersion": next_version},
    )
    if action_name == "request_action":
        publish_confirmed_analysis_summary(db, risk_event=event, actor_id=actor.id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(action)
    db.refresh(event)
    return ActionOutcome(event=event, action=action, duplicate=False)
