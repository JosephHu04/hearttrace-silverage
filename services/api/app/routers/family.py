from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.db.models import (
    DailyInsight,
    EmergencyEvent,
    ElderProfile,
    FamilyActionRecord,
    FamilyElderGrant,
    RiskEvent,
    User,
)
from app.dependencies import DbSession, FamilyActor
from app.schemas import (
    FamilyAccessOut,
    FamilyActionRequest,
    FamilyActionHistoryOut,
    FamilyActionResult,
    FamilyElderListOut,
    FamilyElderOut,
    FamilySafetyOut,
    FamilyStatusOut,
    FamilyTodayOut,
    FamilyTopicOut,
)
from app.services.audit import add_audit_log


router = APIRouter(prefix="/family", tags=["family-care"])


def active_grant(db: DbSession, family_id: str, elder_id: str, scope: str) -> FamilyElderGrant:
    grant = db.get(FamilyElderGrant, (family_id, elder_id))
    if grant is None or not grant.is_active or scope not in grant.scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未获得该老人的有效授权")
    return grant


def elder_out(user: User, profile: ElderProfile) -> FamilyElderOut:
    return FamilyElderOut(id=user.id, name=user.display_name, age=profile.age)


@router.get("/me/elders", response_model=FamilyElderListOut)
def my_elders(db: DbSession, actor: FamilyActor) -> FamilyElderListOut:
    rows = db.execute(
        select(User, ElderProfile)
        .join(FamilyElderGrant, FamilyElderGrant.elder_id == User.id)
        .join(ElderProfile, ElderProfile.user_id == User.id)
        .where(FamilyElderGrant.family_id == actor.id, FamilyElderGrant.is_active.is_(True))
        .order_by(User.display_name)
    ).all()
    return FamilyElderListOut(items=[elder_out(user, profile) for user, profile in rows])


@router.get("/elders/{elder_id}/today", response_model=FamilyTodayOut)
def family_today(elder_id: str, db: DbSession, actor: FamilyActor) -> FamilyTodayOut:
    grant = active_grant(db, actor.id, elder_id, "daily_summary")
    elder = db.get(User, elder_id)
    profile = db.get(ElderProfile, elder_id)
    if elder is None or profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="老人账号不存在")

    insight = db.scalar(
        select(DailyInsight)
        .where(DailyInsight.elder_id == elder_id)
        .order_by(DailyInsight.created_at.desc())
        .limit(1)
    )
    if insight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="尚无可查看的今日摘要")

    risk_event = db.scalar(
        select(RiskEvent)
        .where(RiskEvent.elder_id == elder_id, RiskEvent.status != "closed")
        .order_by(RiskEvent.created_at.desc())
        .limit(1)
    )
    active_emergency = db.scalar(
        select(EmergencyEvent)
        .where(EmergencyEvent.elder_id == elder_id, EmergencyEvent.status.in_({"open", "acknowledged"}))
        .order_by(EmergencyEvent.created_at.desc())
        .limit(1)
    )
    recent_actions = []
    if "care_actions" in grant.scopes:
        recent_actions = list(
            db.scalars(
                select(FamilyActionRecord)
                .join(RiskEvent, RiskEvent.id == FamilyActionRecord.risk_event_id)
                .where(
                    FamilyActionRecord.family_id == actor.id,
                    RiskEvent.elder_id == elder_id,
                )
                .order_by(FamilyActionRecord.created_at.desc())
                .limit(5)
            ).all()
        )
    add_audit_log(
        db,
        actor_id=actor.id,
        action="family.today_viewed",
        target_type="elder",
        target_id=elder_id,
        metadata={"scope": "daily_summary", "content": "structured_summary_only"},
    )
    db.commit()
    return FamilyTodayOut(
        elder=elder_out(elder, profile),
        status=FamilyStatusOut(
            level=insight.level,
            label=insight.label,
            headline=insight.headline,
            summary=insight.summary,
            score=insight.score,
            baseline_delta=insight.baseline_delta,
        ),
        topics=[FamilyTopicOut.model_validate(item) for item in insight.topics],
        safety=FamilySafetyOut(
            has_active_emergency=active_emergency is not None,
            message=(
                "紧急求助已被工作人员确认，正在持续跟进"
                if active_emergency is not None and active_emergency.status == "acknowledged"
                else "老人已发出紧急求助，请尽快确认其安全"
                if active_emergency is not None
                else insight.safety_message
            ),
            status=active_emergency.status if active_emergency is not None else None,
            source=active_emergency.source if active_emergency is not None else None,
            triggered_at=active_emergency.created_at if active_emergency is not None else None,
        ),
        risk_event_id=risk_event.id if risk_event else None,
        access=FamilyAccessOut(
            scopes=grant.scopes,
            care_actions_allowed="care_actions" in grant.scopes,
        ),
        recent_actions=[FamilyActionHistoryOut(action=item.action, recorded_at=item.created_at) for item in recent_actions],
    )


@router.post("/risk-events/{event_id}/actions", response_model=FamilyActionResult)
def record_family_action(
    event_id: str,
    body: FamilyActionRequest,
    db: DbSession,
    actor: FamilyActor,
) -> FamilyActionResult:
    existing = db.scalar(select(FamilyActionRecord).where(FamilyActionRecord.request_id == body.request_id))
    if existing is not None:
        if existing.family_id != actor.id or existing.risk_event_id != event_id or existing.action != body.action.value:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="幂等键已用于其他家属行动")
        return FamilyActionResult(action=existing.action, recorded_at=existing.created_at, duplicate=True)

    event = db.get(RiskEvent, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风险事件不存在")
    active_grant(db, actor.id, event.elder_id, "care_actions")

    record = FamilyActionRecord(
        request_id=body.request_id,
        risk_event_id=event.id,
        family_id=actor.id,
        action=body.action.value,
    )
    db.add(record)
    add_audit_log(
        db,
        actor_id=actor.id,
        action=f"family.{body.action.value}",
        target_type="risk_event",
        target_id=event.id,
        metadata={"elderId": event.elder_id},
    )
    db.commit()
    db.refresh(record)
    return FamilyActionResult(action=record.action, recorded_at=record.created_at)
