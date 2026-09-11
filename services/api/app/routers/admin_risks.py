from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.db.models import AuditLog, RiskAction, RiskEvent, User
from app.dependencies import DbSession, RiskStaff
from app.schemas import (
    AuditListOut,
    AuditLogOut,
    RiskActionOut,
    RiskActionRequest,
    RiskActionResult,
    RiskDetailOut,
    RiskEvidenceOut,
    RiskLevel,
    RiskListItem,
    RiskListOut,
    RiskStatus,
)
from app.services.audit import add_audit_log
from app.services.risks import (
    RiskConflictError,
    RiskNotFoundError,
    apply_action,
    get_risk,
    get_risk_parts,
    list_risks,
)


router = APIRouter(prefix="/admin", tags=["admin-risk-review"])


def list_item(event: RiskEvent, elder_name: str) -> RiskListItem:
    return RiskListItem(
        id=event.id,
        elder_id=event.elder_id,
        elder_name=elder_name,
        level=event.level,
        status=event.status,
        title=event.title,
        assignee_id=event.assignee_id,
        sla_due_at=event.sla_due_at,
        version=event.version,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def action_out(action: RiskAction) -> RiskActionOut:
    return RiskActionOut.model_validate(action)


def detail_out(db: DbSession, event: RiskEvent) -> RiskDetailOut:
    elder_name, evidence, actions = get_risk_parts(db, event)
    base = list_item(event, elder_name).model_dump()
    return RiskDetailOut(
        **base,
        summary=event.summary,
        model_version=event.model_version,
        rule_version=event.rule_version,
        evidence=[RiskEvidenceOut.model_validate(item) for item in evidence],
        actions=[action_out(item) for item in actions],
    )


@router.get("/risk-events", response_model=RiskListOut)
def risk_queue(
    db: DbSession,
    actor: RiskStaff,
    level: Optional[RiskLevel] = None,
    event_status: Optional[RiskStatus] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100, alias="perPage"),
) -> RiskListOut:
    rows, total = list_risks(
        db,
        level=level.value if level else None,
        event_status=event_status.value if event_status else None,
        page=page,
        per_page=per_page,
    )
    return RiskListOut(
        items=[list_item(event, elder_name) for event, elder_name in rows],
        page=page,
        per_page=per_page,
        total=total,
    )


@router.get("/risk-events/{event_id}", response_model=RiskDetailOut)
def risk_detail(event_id: str, db: DbSession, actor: RiskStaff) -> RiskDetailOut:
    try:
        event = get_risk(db, event_id)
    except RiskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风险事件不存在") from exc

    add_audit_log(
        db,
        actor_id=actor.id,
        action="risk.viewed",
        target_type="risk_event",
        target_id=event.id,
        metadata={"evidenceScope": "structured_only"},
    )
    db.commit()
    return detail_out(db, event)


@router.post("/risk-events/{event_id}/actions", response_model=RiskActionResult)
def risk_action(event_id: str, body: RiskActionRequest, db: DbSession, actor: RiskStaff) -> RiskActionResult:
    try:
        outcome = apply_action(db, event_id=event_id, actor=actor, request=body)
    except RiskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风险事件不存在") from exc
    except RiskConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return RiskActionResult(
        event=detail_out(db, outcome.event),
        action=action_out(outcome.action),
        duplicate=outcome.duplicate,
    )


@router.get("/audit-logs", response_model=AuditListOut)
def audit_logs(
    db: DbSession,
    actor: RiskStaff,
    actor_id: Optional[str] = Query(default=None, alias="actorId", max_length=64),
    action: Optional[str] = Query(default=None, max_length=64),
    target_type: Optional[str] = Query(default=None, alias="targetType"),
    target_id: Optional[str] = Query(default=None, alias="targetId"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100, alias="perPage"),
) -> AuditListOut:
    filters = []
    if actor_id:
        filters.append(AuditLog.actor_id == actor_id)
    if action:
        filters.append(AuditLog.action == action)
    if target_type:
        filters.append(AuditLog.target_type == target_type)
    if target_id:
        filters.append(AuditLog.target_id == target_id)
    total = db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    rows = list(
        db.execute(
            select(AuditLog, User.display_name)
            .join(User, User.id == AuditLog.actor_id)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    )
    return AuditListOut(
        items=[
            AuditLogOut(
                id=entry.id,
                actor_id=entry.actor_id,
                actor_display_name=actor_display_name,
                action=entry.action,
                target_type=entry.target_type,
                target_id=entry.target_id,
                metadata=entry.metadata_json,
                created_at=entry.created_at,
            )
            for entry, actor_display_name in rows
        ],
        page=page,
        per_page=per_page,
        total=total,
    )
