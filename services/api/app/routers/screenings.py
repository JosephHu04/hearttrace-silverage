"""Consent-controlled, deterministic mental-health screening workflow."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.db.models import RiskEvent, RiskEvidence, ScreeningAnswer, ScreeningSession, User, utc_now
from app.dependencies import CurrentActor, DbSession, ElderActor, FamilyActor, RiskStaff
from app.routers.family import active_grant
from app.schemas import (
    ScreeningAnswerRequest,
    ScreeningInstrumentListOut,
    ScreeningSessionListOut,
    ScreeningSessionOut,
    ScreeningStartRequest,
    ScreeningSummaryListOut,
    ScreeningSummaryOut,
)
from app.services.audit import add_audit_log
from app.services.notifications import notify_families, notify_staff
from app.services.screenings import (
    INSTRUMENTS,
    INSTRUMENT_VERSION,
    SCREENING_NOTICE,
    get_instrument,
    instrument_payload,
    question_payload,
    result_payload,
    score_response,
)


router = APIRouter(tags=["standard-screenings"])
RULE_VERSION = "screening-wst802-2022-v1"


def _session_out(db: DbSession, session: ScreeningSession) -> ScreeningSessionOut:
    instrument = get_instrument(session.instrument_code)
    answers = list(
        db.scalars(
            select(ScreeningAnswer)
            .where(ScreeningAnswer.session_id == session.id)
            .order_by(ScreeningAnswer.answered_at, ScreeningAnswer.id)
        )
    )
    result = result_payload(session.instrument_code, session.total_score) if session.total_score is not None else None
    return ScreeningSessionOut.model_validate(
        {
            "id": session.id,
            "elderId": session.elder_id,
            "instrument": instrument_payload(instrument),
            "status": session.status,
            "progressAnswered": len(answers),
            "shareWithFamily": session.share_with_family,
            "shareWithCareTeam": session.share_with_care_team,
            "currentQuestion": question_payload(instrument, len(answers)) if session.status == "in_progress" else None,
            "result": result,
            "consentAt": session.consent_at,
            "completedAt": session.completed_at,
            "createdAt": session.created_at,
        }
    )


def _summary(row: ScreeningSession, elder_name: str) -> ScreeningSummaryOut:
    instrument = get_instrument(row.instrument_code)
    result = result_payload(row.instrument_code, row.total_score) if row.total_score is not None else None
    return ScreeningSummaryOut(
        id=row.id,
        elder_id=row.elder_id,
        elder_name=elder_name,
        instrument_code=row.instrument_code,
        instrument_name=instrument.name,
        status=row.status,
        band=result["band"] if result else None,
        label=str(result["label"]) if result else "进行中",
        recommendation=row.recommendation,
        completed_at=row.completed_at,
        created_at=row.created_at,
    )


def _create_follow_up(db: DbSession, session: ScreeningSession, elder_name: str) -> None:
    if session.result_band not in {"moderate", "high"} or not session.share_with_care_team:
        return
    event_id = f"risk-screening-{session.id}"
    if db.get(RiskEvent, event_id) is not None:
        return
    level = "yellow" if session.result_band == "moderate" else "orange"
    instrument = get_instrument(session.instrument_code)
    event = RiskEvent(
        id=event_id,
        elder_id=session.elder_id,
        level=level,
        status="new",
        title=f"{instrument.name}提示需要人工复核",
        summary=f"{elder_name}已完成{instrument.name}，结果达到人工关注范围。该结果为标准化筛查提示，不是疾病诊断。",
        model_version=None,
        rule_version=RULE_VERSION,
        sla_due_at=utc_now() + timedelta(hours=2 if session.result_band == "high" else 24),
    )
    db.add(event)
    db.flush()
    db.add(
        RiskEvidence(
            risk_event_id=event.id,
            source_type="screening",
            label="标准化量表",
            detail=(
                f"{instrument.name}得分 {session.total_score}，"
                f"按 {instrument.standard_reference} 分层为"
                f"{'需要人工关注' if session.result_band == 'moderate' else '需要尽快人工评估'}。"
            ),
            evidence_ref=session.id,
        )
    )
    notify_staff(
        db,
        category="risk_follow_up",
        title="新的标准筛查复核事项",
        body=f"{elder_name}的{instrument.name}已进入人工复核队列。",
        target_type="risk_event",
        target_id=event.id,
        event_key="screening-completed",
    )


@router.get("/screenings/instruments", response_model=ScreeningInstrumentListOut)
def list_instruments(actor: CurrentActor) -> ScreeningInstrumentListOut:
    del actor
    return ScreeningInstrumentListOut(
        items=[instrument_payload(instrument) for instrument in INSTRUMENTS.values()],
        notice=SCREENING_NOTICE,
    )


@router.post("/elder/screenings", response_model=ScreeningSessionOut, status_code=status.HTTP_201_CREATED)
def start_screening(body: ScreeningStartRequest, db: DbSession, elder: ElderActor) -> ScreeningSessionOut:
    if not body.consent_confirmed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="请在本人知情同意后开始筛查")
    instrument = get_instrument(body.instrument_code.value)
    session = ScreeningSession(
        elder_id=elder.id,
        instrument_code=instrument.code,
        instrument_version=INSTRUMENT_VERSION,
        standard_reference=instrument.standard_reference,
        share_with_family=body.share_with_family,
        share_with_care_team=body.share_with_care_team,
    )
    db.add(session)
    db.flush()
    add_audit_log(
        db,
        actor_id=elder.id,
        action="screening.started",
        target_type="screening_session",
        target_id=session.id,
        metadata={
            "instrumentCode": instrument.code,
            "instrumentVersion": INSTRUMENT_VERSION,
            "shareWithFamily": session.share_with_family,
            "shareWithCareTeam": session.share_with_care_team,
        },
    )
    db.commit()
    db.refresh(session)
    return _session_out(db, session)


@router.get("/elder/screenings", response_model=ScreeningSessionListOut)
def my_screenings(db: DbSession, elder: ElderActor, limit: int = Query(default=10, ge=1, le=50)) -> ScreeningSessionListOut:
    rows = list(
        db.scalars(
            select(ScreeningSession)
            .where(ScreeningSession.elder_id == elder.id)
            .order_by(ScreeningSession.created_at.desc())
            .limit(limit)
        )
    )
    return ScreeningSessionListOut(items=[_session_out(db, row) for row in rows])


@router.post("/elder/screenings/{session_id}/answers", response_model=ScreeningSessionOut)
def answer_screening(
    session_id: str,
    body: ScreeningAnswerRequest,
    db: DbSession,
    elder: ElderActor,
) -> ScreeningSessionOut:
    session = db.get(ScreeningSession, session_id)
    if session is None or session.elder_id != elder.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="筛查记录不存在")
    instrument = get_instrument(session.instrument_code)
    existing_answers = list(
        db.scalars(
            select(ScreeningAnswer)
            .where(ScreeningAnswer.session_id == session.id)
            .order_by(ScreeningAnswer.answered_at, ScreeningAnswer.id)
        )
    )

    duplicate = next((answer for answer in existing_answers if answer.item_code == body.item_code), None)
    if duplicate is not None:
        if duplicate.response_value != body.value:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该题已经作答，不能通过重试改写")
        return _session_out(db, session)
    if session.status != "in_progress":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该筛查已经完成")

    expected = instrument.items[len(existing_answers)] if len(existing_answers) < len(instrument.items) else None
    if expected is None or body.item_code != expected.code:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="题目顺序不匹配，请刷新后继续")
    try:
        score = score_response(instrument, body.item_code, body.value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.add(
        ScreeningAnswer(
            session_id=session.id,
            item_code=body.item_code,
            response_value=body.value,
            score_value=score,
        )
    )
    if len(existing_answers) + 1 == len(instrument.items):
        total = sum(answer.score_value for answer in existing_answers) + score
        result = result_payload(instrument.code, total)
        session.status = "completed"
        session.total_score = total
        session.result_band = str(result["band"])
        session.recommendation = str(result["recommendation"])
        session.completed_at = utc_now()
        session.updated_at = session.completed_at
        elder_name = db.scalar(select(User.display_name).where(User.id == elder.id)) or "老人"
        _create_follow_up(db, session, elder_name)
        if session.share_with_family:
            notify_families(
                db,
                elder_id=session.elder_id,
                required_scope="daily_summary",
                category="analysis_summary",
                title="标准关怀筛查已完成",
                body=f"{elder_name}已完成{instrument.name}，可查看关怀建议。",
                target_type="screening_session",
                target_id=session.id,
                event_key="screening-completed",
            )
        add_audit_log(
            db,
            actor_id=elder.id,
            action="screening.completed",
            target_type="screening_session",
            target_id=session.id,
            metadata={
                "instrumentCode": instrument.code,
                "instrumentVersion": session.instrument_version,
                "resultBand": session.result_band,
                "shareWithFamily": session.share_with_family,
                "shareWithCareTeam": session.share_with_care_team,
            },
        )
    db.commit()
    db.refresh(session)
    return _session_out(db, session)


@router.get("/family/elders/{elder_id}/screenings", response_model=ScreeningSummaryListOut)
def family_screenings(
    elder_id: str,
    db: DbSession,
    family: FamilyActor,
    days: int = Query(default=30, ge=1, le=365),
) -> ScreeningSummaryListOut:
    active_grant(db, family.id, elder_id, "daily_summary")
    cutoff = utc_now() - timedelta(days=days)
    elder_name = db.scalar(select(User.display_name).where(User.id == elder_id))
    if elder_name is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="老人账号不存在")
    rows = list(
        db.scalars(
            select(ScreeningSession)
            .where(
                ScreeningSession.elder_id == elder_id,
                ScreeningSession.status == "completed",
                ScreeningSession.share_with_family.is_(True),
                ScreeningSession.completed_at >= cutoff,
            )
            .order_by(ScreeningSession.completed_at.desc())
        )
    )
    add_audit_log(
        db,
        actor_id=family.id,
        action="family.screenings_viewed",
        target_type="elder",
        target_id=elder_id,
        metadata={"days": days, "content": "summary_only_no_answers"},
    )
    db.commit()
    return ScreeningSummaryListOut(items=[_summary(row, elder_name) for row in rows], total=len(rows))


@router.get("/admin/screenings", response_model=ScreeningSummaryListOut)
def staff_screenings(
    db: DbSession,
    staff: RiskStaff,
    band: str | None = Query(default=None, pattern="^(normal|moderate|high)$"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100, alias="perPage"),
) -> ScreeningSummaryListOut:
    filters = [ScreeningSession.share_with_care_team.is_(True)]
    if band is not None:
        filters.append(ScreeningSession.result_band == band)
    total = db.scalar(select(func.count()).select_from(ScreeningSession).where(*filters)) or 0
    rows = list(
        db.execute(
            select(ScreeningSession, User.display_name)
            .join(User, User.id == ScreeningSession.elder_id)
            .where(*filters)
            .order_by(ScreeningSession.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    )
    add_audit_log(
        db,
        actor_id=staff.id,
        action="screening.queue_viewed",
        target_type="screening_queue",
        target_id=band or "all",
        metadata={"page": page, "content": "structured_result_only_no_answers"},
    )
    db.commit()
    return ScreeningSummaryListOut(items=[_summary(row, name) for row, name in rows], total=total)
