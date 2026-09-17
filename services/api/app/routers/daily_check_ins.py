"""Consent-controlled daily self-reports; never a diagnostic score."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import DailyCheckIn, User, utc_now
from app.dependencies import DbSession, ElderActor, FamilyActor, RiskStaff
from app.routers.family import active_grant
from app.schemas import (
    DailyCheckInCreate,
    DailyCheckInListOut,
    DailyCheckInOut,
    DailyCheckInSharingUpdate,
    SharedCheckInListOut,
    SharedCheckInOut,
    StaffCheckInListOut,
    StaffCheckInOut,
)
from app.services.audit import add_audit_log


router = APIRouter(tags=["daily-check-ins"])
CARE_DAY_ZONE = ZoneInfo("Asia/Shanghai")


def _care_day() -> date:
    return datetime.now(CARE_DAY_ZONE).date()


def _start_day(days: int) -> date:
    return _care_day() - timedelta(days=days - 1)


def _apply_check_in(row: DailyCheckIn, body: DailyCheckInCreate) -> bool:
    changed = False
    for key in ("mood", "sleep", "social_willingness", "share_with_family", "share_with_care_team"):
        value = getattr(body, key)
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed = True
    if changed:
        row.updated_at = utc_now()
    return changed


@router.post("/elder/check-ins", response_model=DailyCheckInOut)
def save_my_check_in(body: DailyCheckInCreate, db: DbSession, elder: ElderActor) -> DailyCheckInOut:
    today = _care_day()
    row = db.scalar(select(DailyCheckIn).where(DailyCheckIn.elder_id == elder.id, DailyCheckIn.checkin_date == today))
    if row is None:
        row = DailyCheckIn(elder_id=elder.id, checkin_date=today, **body.model_dump())
        db.add(row)
        try:
            db.flush()
            action = "daily_check_in.created"
        except IntegrityError:
            # Another device may have submitted the same day's first check-in.
            db.rollback()
            row = db.scalar(select(DailyCheckIn).where(DailyCheckIn.elder_id == elder.id, DailyCheckIn.checkin_date == today))
            if row is None:
                raise
            action = "daily_check_in.updated" if _apply_check_in(row, body) else None
    else:
        action = "daily_check_in.updated" if _apply_check_in(row, body) else None

    if action is not None:
        add_audit_log(
            db,
            actor_id=elder.id,
            action=action,
            target_type="daily_check_in",
            target_id=row.id,
            metadata={
                "shareWithFamily": row.share_with_family,
                "shareWithCareTeam": row.share_with_care_team,
                "checkinDate": today.isoformat(),
            },
        )
        db.commit()
    return DailyCheckInOut.model_validate(row)


@router.get("/elder/check-ins", response_model=DailyCheckInListOut)
def my_check_ins(db: DbSession, elder: ElderActor, days: int = Query(default=7, ge=1, le=30)) -> DailyCheckInListOut:
    rows = db.scalars(
        select(DailyCheckIn)
        .where(DailyCheckIn.elder_id == elder.id, DailyCheckIn.checkin_date >= _start_day(days))
        .order_by(DailyCheckIn.checkin_date.desc())
    ).all()
    return DailyCheckInListOut(items=[DailyCheckInOut.model_validate(row) for row in rows])


@router.post("/elder/check-ins/{checkin_id}/sharing", response_model=DailyCheckInOut)
def update_check_in_sharing(
    checkin_id: str, body: DailyCheckInSharingUpdate, db: DbSession, elder: ElderActor
) -> DailyCheckInOut:
    row = db.get(DailyCheckIn, checkin_id)
    if row is None or row.elder_id != elder.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="打卡记录不存在")
    if row.share_with_family != body.share_with_family or row.share_with_care_team != body.share_with_care_team:
        row.share_with_family = body.share_with_family
        row.share_with_care_team = body.share_with_care_team
        row.updated_at = utc_now()
        add_audit_log(
            db,
            actor_id=elder.id,
            action="daily_check_in.sharing_updated",
            target_type="daily_check_in",
            target_id=row.id,
            metadata={
                "shareWithFamily": row.share_with_family,
                "shareWithCareTeam": row.share_with_care_team,
                "checkinDate": row.checkin_date.isoformat(),
            },
        )
        db.commit()
    return DailyCheckInOut.model_validate(row)


@router.get("/family/elders/{elder_id}/check-ins", response_model=SharedCheckInListOut)
def family_check_ins(
    elder_id: str,
    db: DbSession,
    family: FamilyActor,
    days: int = Query(default=7, ge=1, le=30),
) -> SharedCheckInListOut:
    # Check the live grant on every read; revocation must take effect immediately.
    active_grant(db, family.id, elder_id, "daily_summary")
    rows = db.scalars(
        select(DailyCheckIn)
        .where(
            DailyCheckIn.elder_id == elder_id,
            DailyCheckIn.checkin_date >= _start_day(days),
            DailyCheckIn.share_with_family.is_(True),
        )
        .order_by(DailyCheckIn.checkin_date.asc())
    ).all()
    add_audit_log(
        db,
        actor_id=family.id,
        action="family.check_ins_viewed",
        target_type="elder",
        target_id=elder_id,
        metadata={"days": days, "content": "elder_shared_self_report_only"},
    )
    db.commit()
    return SharedCheckInListOut(items=[SharedCheckInOut.model_validate(row) for row in rows])


@router.get("/admin/check-ins", response_model=StaffCheckInListOut)
def staff_check_ins(
    db: DbSession,
    staff: RiskStaff,
    days: int = Query(default=7, ge=1, le=30),
    attention_only: bool = Query(default=False, alias="attentionOnly"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100, alias="perPage"),
) -> StaffCheckInListOut:
    filters = [DailyCheckIn.checkin_date >= _start_day(days), DailyCheckIn.share_with_care_team.is_(True)]
    if attention_only:
        filters.append(
            (DailyCheckIn.mood <= 2) | (DailyCheckIn.sleep <= 2) | (DailyCheckIn.social_willingness <= 2)
        )
    total = db.scalar(select(func.count()).select_from(DailyCheckIn).where(*filters)) or 0
    rows = db.execute(
        select(DailyCheckIn, User.display_name)
        .join(User, User.id == DailyCheckIn.elder_id)
        .where(*filters)
        .order_by(DailyCheckIn.checkin_date.desc(), DailyCheckIn.created_at.desc(), DailyCheckIn.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()
    add_audit_log(
        db,
        actor_id=staff.id,
        action="daily_check_in.queue_viewed",
        target_type="daily_check_in_queue",
        target_id="shared",
        metadata={"days": days, "attentionOnly": attention_only, "page": page},
    )
    db.commit()
    return StaffCheckInListOut(
        items=[
            StaffCheckInOut(
                id=row.id,
                elder_id=row.elder_id,
                elder_name=name,
                checkin_date=row.checkin_date,
                mood=row.mood,
                sleep=row.sleep,
                social_willingness=row.social_willingness,
                attention_needed=min(row.mood, row.sleep, row.social_willingness) <= 2,
            )
            for row, name in rows
        ],
        total=total,
    )
