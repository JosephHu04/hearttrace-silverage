from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.db.models import RegistrationApplication, User, utc_now, uuid_string
from app.dependencies import DbSession, RiskStaff
from app.schemas import (
    RegistrationApplicationListOut,
    RegistrationApplicationOut,
    RegistrationReviewRequest,
    RegistrationStatus,
)
from app.services.audit import add_audit_log


router = APIRouter(prefix="/admin", tags=["admin-account-approval"])


def application_out(application: RegistrationApplication) -> RegistrationApplicationOut:
    return RegistrationApplicationOut(
        id=application.id,
        display_name=application.display_name,
        login_identifier=application.login_identifier,
        relationship=application.relationship,
        elder_name=application.elder_name,
        consent_version=application.consent_version,
        status=RegistrationStatus(application.status),
        review_note=application.review_note,
        reviewed_at=application.reviewed_at,
        created_at=application.created_at,
    )


@router.get("/registration-applications", response_model=RegistrationApplicationListOut)
def registration_applications(
    db: DbSession,
    actor: RiskStaff,
    application_status: RegistrationStatus = Query(default=RegistrationStatus.pending, alias="status"),
) -> RegistrationApplicationListOut:
    statement = select(RegistrationApplication).where(RegistrationApplication.status == application_status.value)
    items = list(db.scalars(statement.order_by(RegistrationApplication.created_at.asc())))
    total = db.scalar(select(func.count()).select_from(RegistrationApplication).where(RegistrationApplication.status == application_status.value)) or 0
    return RegistrationApplicationListOut(items=[application_out(item) for item in items], total=total)


@router.post("/registration-applications/{application_id}/review", response_model=RegistrationApplicationOut)
def review_registration_application(
    application_id: str,
    body: RegistrationReviewRequest,
    db: DbSession,
    actor: RiskStaff,
) -> RegistrationApplicationOut:
    if body.decision not in {RegistrationStatus.approved, RegistrationStatus.rejected}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="审核结果只能是通过或驳回")
    application = db.get(RegistrationApplication, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="注册申请不存在")
    if application.status != RegistrationStatus.pending.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该申请已处理，请刷新列表")

    if body.decision is RegistrationStatus.approved:
        existing = db.scalar(select(User).where(User.login_identifier == application.login_identifier))
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该联系方式已绑定账号")
        db.add(
            User(
                id=f"family-{uuid_string()}",
                display_name=application.display_name,
                role="family",
                is_active=True,
                login_identifier=application.login_identifier,
                password_hash=application.password_hash,
                password_changed_at=utc_now(),
            )
        )

    application.status = body.decision.value
    application.reviewed_by = actor.id
    application.review_note = body.note.strip() if body.note else None
    application.reviewed_at = utc_now()
    add_audit_log(
        db,
        actor_id=actor.id,
        action=f"registration.{body.decision.value}",
        target_type="registration_application",
        target_id=application.id,
        metadata={"loginIdentifier": application.login_identifier, "relationship": application.relationship},
    )
    db.commit()
    db.refresh(application)
    return application_out(application)
