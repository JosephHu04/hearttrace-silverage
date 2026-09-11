from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import aliased

from app.db.models import ElderProfile, FamilyElderGrant, RegistrationApplication, User, utc_now, uuid_string
from app.dependencies import AdminActor, DbSession
from app.schemas import (
    ElderAccountListOut,
    ElderAccountOut,
    FamilyGrantListOut,
    FamilyGrantOut,
    GrantActionRequest,
    GrantActionType,
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
    actor: AdminActor,
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
    actor: AdminActor,
) -> RegistrationApplicationOut:
    if body.decision not in {RegistrationStatus.approved, RegistrationStatus.rejected}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="审核结果只能是通过或驳回")
    application = db.get(RegistrationApplication, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="注册申请不存在")
    if application.status != RegistrationStatus.pending.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该申请已处理，请刷新列表")

    if body.decision is RegistrationStatus.approved:
        if body.elder_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="通过申请前必须选择已核验的老人账号")
        if not body.scopes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="授权范围不能为空")
        elder = db.get(User, body.elder_id)
        if elder is None or elder.role != "elder" or not elder.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="老人账号不存在或已停用")
        existing = db.scalar(select(User).where(User.login_identifier == application.login_identifier))
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该联系方式已绑定账号")
        family = User(
            id=f"family-{uuid_string()}",
            display_name=application.display_name,
            role="family",
            is_active=True,
            login_identifier=application.login_identifier,
            password_hash=application.password_hash,
            password_changed_at=utc_now(),
        )
        db.add(family)
        db.flush()
        now = utc_now()
        scopes = list(dict.fromkeys(scope.value for scope in body.scopes))
        db.add(
            FamilyElderGrant(
                family_id=family.id,
                elder_id=elder.id,
                scopes=scopes,
                is_active=True,
                relationship=application.relationship,
                consent_version=application.consent_version,
                created_by=actor.id,
                updated_by=actor.id,
                created_at=now,
                updated_at=now,
            )
        )
        application.elder_id = elder.id
        add_audit_log(
            db,
            actor_id=actor.id,
            action="grant.created",
            target_type="family_elder_grant",
            target_id=f"{family.id}:{elder.id}",
            metadata={"familyId": family.id, "elderId": elder.id, "scopes": scopes, "consentVersion": application.consent_version},
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


@router.get("/elders", response_model=ElderAccountListOut)
def elder_accounts(db: DbSession, actor: AdminActor) -> ElderAccountListOut:
    rows = db.execute(
        select(User, ElderProfile)
        .join(ElderProfile, ElderProfile.user_id == User.id)
        .where(User.role == "elder", User.is_active.is_(True))
        .order_by(User.display_name)
    ).all()
    return ElderAccountListOut(items=[ElderAccountOut(id=user.id, display_name=user.display_name, age=profile.age) for user, profile in rows])


def grant_out(grant: FamilyElderGrant, family_name: str, elder_name: str) -> FamilyGrantOut:
    return FamilyGrantOut(
        family_id=grant.family_id,
        family_name=family_name,
        elder_id=grant.elder_id,
        elder_name=elder_name,
        relationship=grant.relationship,
        consent_version=grant.consent_version,
        scopes=grant.scopes,
        is_active=grant.is_active,
        version=grant.version,
        created_at=grant.created_at,
        updated_at=grant.updated_at,
        revoked_at=grant.revoked_at,
    )


@router.get("/family-grants", response_model=FamilyGrantListOut)
def family_grants(
    db: DbSession,
    actor: AdminActor,
    active: Optional[bool] = Query(default=None),
) -> FamilyGrantListOut:
    family_user = aliased(User)
    elder_user = aliased(User)
    filters = [FamilyElderGrant.is_active == active] if active is not None else []
    rows = db.execute(
        select(FamilyElderGrant, family_user.display_name, elder_user.display_name)
        .join(family_user, family_user.id == FamilyElderGrant.family_id)
        .join(elder_user, elder_user.id == FamilyElderGrant.elder_id)
        .where(*filters)
        .order_by(FamilyElderGrant.updated_at.desc())
    ).all()
    return FamilyGrantListOut(
        items=[grant_out(grant, family_name, elder_name) for grant, family_name, elder_name in rows],
        total=len(rows),
    )


@router.post("/family-grants/{family_id}/{elder_id}/actions", response_model=FamilyGrantOut)
def change_family_grant(
    family_id: str,
    elder_id: str,
    body: GrantActionRequest,
    db: DbSession,
    actor: AdminActor,
) -> FamilyGrantOut:
    grant = db.get(FamilyElderGrant, (family_id, elder_id))
    if grant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="授权关系不存在")
    if grant.version != body.expected_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"授权已更新，当前版本为 {grant.version}")

    note = (body.note or "").strip()
    now = utc_now()
    values: dict[str, object] = {"updated_by": actor.id, "updated_at": now, "version": grant.version + 1}
    if body.action is GrantActionType.update_scopes:
        if not body.scopes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="授权范围不能为空")
        if not grant.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已撤销授权不能直接调整范围")
        values["scopes"] = list(dict.fromkeys(scope.value for scope in body.scopes))
    elif body.action is GrantActionType.revoke:
        if not grant.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="授权已经撤销")
        if not note:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="撤销授权必须填写说明")
        values.update({"is_active": False, "revoked_by": actor.id, "revoked_at": now})
    else:
        if grant.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="授权当前已经生效")
        if not note:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="重新启用授权必须填写说明")
        values.update({"is_active": True, "revoked_by": None, "revoked_at": None})

    result = db.execute(
        update(FamilyElderGrant)
        .where(
            FamilyElderGrant.family_id == family_id,
            FamilyElderGrant.elder_id == elder_id,
            FamilyElderGrant.version == body.expected_version,
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="授权已被其他管理员更新")
    add_audit_log(
        db,
        actor_id=actor.id,
        action=f"grant.{body.action.value}",
        target_type="family_elder_grant",
        target_id=f"{family_id}:{elder_id}",
        metadata={"familyId": family_id, "elderId": elder_id, "scopes": values.get("scopes", grant.scopes), "note": note or None, "version": grant.version + 1},
    )
    db.commit()
    db.refresh(grant)
    family_name = db.scalar(select(User.display_name).where(User.id == family_id))
    elder_name = db.scalar(select(User.display_name).where(User.id == elder_id))
    if family_name is None or elder_name is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联账号不存在")
    return grant_out(grant, family_name, elder_name)
