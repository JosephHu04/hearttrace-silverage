from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.db.models import (
    DailyInsight,
    EmergencyEvent,
    ElderProfile,
    FamilyActionRecord,
    FamilyCarePlanItem,
    FamilyElderGrant,
    RiskEvent,
    User,
    utc_now,
)
from app.dependencies import DbSession, FamilyActor
from app.schemas import (
    FamilyAccessOut,
    FamilyActionRequest,
    FamilyActionHistoryOut,
    FamilyActionResult,
    FamilyCarePlanItemCreate,
    FamilyCarePlanItemOut,
    FamilyElderListOut,
    FamilyElderOut,
    FamilySafetyOut,
    FamilyStatusOut,
    FamilyTodayOut,
    FamilyTopicOut,
    FamilyTrendOut,
    FamilyTrendPointOut,
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


@router.get("/elders/{elder_id}/trend", response_model=FamilyTrendOut)
def family_trend(
    elder_id: str,
    db: DbSession,
    actor: FamilyActor,
    days: int = Query(default=7, ge=1, le=30),
) -> FamilyTrendOut:
    """Return only approved, daily-level summaries; never conversation content."""
    active_grant(db, actor.id, elder_id, "daily_summary")
    cutoff = utc_now() - timedelta(days=days)
    insights = list(
        db.scalars(
            select(DailyInsight)
            .where(DailyInsight.elder_id == elder_id, DailyInsight.created_at >= cutoff)
            .order_by(DailyInsight.created_at.asc())
        )
    )
    add_audit_log(
        db,
        actor_id=actor.id,
        action="family.trend_viewed",
        target_type="elder",
        target_id=elder_id,
        metadata={"scope": "daily_summary", "days": days, "content": "daily_scores_only"},
    )
    db.commit()
    return FamilyTrendOut(
        period_days=days,
        items=[
            FamilyTrendPointOut(
                recorded_at=item.created_at,
                score=item.score,
                level=item.level,
                label=item.label,
            )
            for item in insights
        ],
    )


@router.get("/elders/{elder_id}/care-plan", response_model=list[FamilyCarePlanItemOut])
def list_care_plan(elder_id: str, db: DbSession, actor: FamilyActor) -> list[FamilyCarePlanItemOut]:
    active_grant(db, actor.id, elder_id, "daily_summary")
    items = list(
        db.scalars(
            select(FamilyCarePlanItem)
            .where(FamilyCarePlanItem.family_id == actor.id, FamilyCarePlanItem.elder_id == elder_id)
            .order_by(FamilyCarePlanItem.completed_at.is_not(None), FamilyCarePlanItem.scheduled_for, FamilyCarePlanItem.created_at)
        )
    )
    add_audit_log(
        db,
        actor_id=actor.id,
        action="family.care_plan_viewed",
        target_type="elder",
        target_id=elder_id,
        metadata={"scope": "daily_summary", "content": "own_plan_only"},
    )
    db.commit()
    return [FamilyCarePlanItemOut.model_validate(item) for item in items]


@router.post("/elders/{elder_id}/care-plan", response_model=FamilyCarePlanItemOut, status_code=status.HTTP_201_CREATED)
def create_care_plan_item(
    elder_id: str,
    body: FamilyCarePlanItemCreate,
    db: DbSession,
    actor: FamilyActor,
) -> FamilyCarePlanItemOut:
    active_grant(db, actor.id, elder_id, "care_actions")
    item = FamilyCarePlanItem(
        family_id=actor.id,
        elder_id=elder_id,
        title=body.title.strip(),
        scheduled_for=body.scheduled_for,
    )
    db.add(item)
    db.flush()
    add_audit_log(
        db,
        actor_id=actor.id,
        action="family.care_plan_created",
        target_type="family_care_plan_item",
        target_id=item.id,
        metadata={"elderId": elder_id},
    )
    db.commit()
    db.refresh(item)
    return FamilyCarePlanItemOut.model_validate(item)


@router.post("/elders/{elder_id}/care-plan/{item_id}/complete", response_model=FamilyCarePlanItemOut)
def complete_care_plan_item(
    elder_id: str,
    item_id: str,
    db: DbSession,
    actor: FamilyActor,
) -> FamilyCarePlanItemOut:
    active_grant(db, actor.id, elder_id, "care_actions")
    item = db.get(FamilyCarePlanItem, item_id)
    if item is None or item.family_id != actor.id or item.elder_id != elder_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关怀计划不存在")
    if item.completed_at is None:
        item.completed_at = utc_now()
        add_audit_log(
            db,
            actor_id=actor.id,
            action="family.care_plan_completed",
            target_type="family_care_plan_item",
            target_id=item.id,
            metadata={"elderId": elder_id},
        )
        db.commit()
        db.refresh(item)
    return FamilyCarePlanItemOut.model_validate(item)


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
