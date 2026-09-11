from datetime import timedelta
import secrets

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.security import create_access_token, hash_one_time_token, hash_password, verify_password
from app.db.models import PasswordRecoveryToken, RegistrationApplication, User, utc_now, uuid_string
from app.dependencies import CurrentActor, DbSession
from app.schemas import (
    ActorOut,
    DemoLoginRequest,
    LoginRequest,
    MessageOut,
    PasswordChangeRequest,
    PasswordRecoveryConfirm,
    PasswordRecoveryRequest,
    RegistrationApplicationCreate,
    RegistrationApplicationOut,
    RegistrationStatus,
    TokenOut,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def normalize_identifier(value: str) -> str:
    return value.strip().lower()


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


@router.post("/demo-login", response_model=TokenOut)
def demo_login(body: DemoLoginRequest, db: DbSession) -> TokenOut:
    actor = db.get(User, body.actor_id)
    if actor is None or not actor.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="演示账号不存在或已停用")

    access_token, expires_at = create_access_token(actor_id=actor.id, role=actor.role)
    return TokenOut(
        access_token=access_token,
        expires_at=expires_at,
        actor=ActorOut.model_validate(actor),
    )


@router.post("/registration-applications", response_model=RegistrationApplicationOut, status_code=status.HTTP_201_CREATED)
def create_registration_application(body: RegistrationApplicationCreate, db: DbSession) -> RegistrationApplicationOut:
    identifier = normalize_identifier(body.login_identifier)
    existing_user = db.scalar(select(User).where(User.login_identifier == identifier))
    existing_application = db.scalar(select(RegistrationApplication).where(RegistrationApplication.login_identifier == identifier))
    if existing_user is not None or existing_application is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该联系方式已提交过申请或已绑定账号")

    application = RegistrationApplication(
        display_name=body.display_name.strip(),
        login_identifier=identifier,
        relationship=body.relationship.strip(),
        elder_name=body.elder_name.strip(),
        password_hash=hash_password(body.password),
        consent_version=body.consent_version,
        status=RegistrationStatus.pending.value,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application_out(application)


@router.get("/registration-applications/{application_id}", response_model=RegistrationApplicationOut)
def registration_application_status(application_id: str, db: DbSession) -> RegistrationApplicationOut:
    application = db.get(RegistrationApplication, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该注册申请")
    return application_out(application)


@router.post("/login", response_model=TokenOut)
def login(body: LoginRequest, db: DbSession) -> TokenOut:
    identifier = normalize_identifier(body.login_identifier)
    actor = db.scalar(select(User).where(User.login_identifier == identifier))
    if actor is None or not actor.is_active or not verify_password(body.password, actor.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录凭据或密码不正确")
    access_token, expires_at = create_access_token(actor_id=actor.id, role=actor.role)
    return TokenOut(access_token=access_token, expires_at=expires_at, actor=ActorOut.model_validate(actor))


@router.post("/password/change", response_model=MessageOut)
def change_password(body: PasswordChangeRequest, db: DbSession, actor: CurrentActor) -> MessageOut:
    if not verify_password(body.current_password, actor.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码不正确")
    actor.password_hash = hash_password(body.new_password)
    actor.password_changed_at = utc_now()
    db.commit()
    return MessageOut(message="密码已更新，请在其他设备重新登录")


@router.post("/password-recovery", response_model=MessageOut)
def request_password_recovery(body: PasswordRecoveryRequest, db: DbSession) -> MessageOut:
    identifier = normalize_identifier(body.login_identifier)
    actor = db.scalar(select(User).where(User.login_identifier == identifier))
    if actor is not None and actor.is_active:
        raw_token = secrets.token_urlsafe(32)
        db.add(
            PasswordRecoveryToken(
                user_id=actor.id,
                token_hash=hash_one_time_token(raw_token),
                expires_at=utc_now() + timedelta(minutes=15),
            )
        )
        db.commit()
        # Delivery is intentionally delegated to the configured email/SMS adapter.
        # Never return the raw recovery token from this public endpoint.
    return MessageOut(message="如该联系方式已注册，重置说明将发送至已绑定渠道")


@router.post("/password-recovery/confirm", response_model=MessageOut)
def confirm_password_recovery(body: PasswordRecoveryConfirm, db: DbSession) -> MessageOut:
    now = utc_now()
    recovery = db.scalar(
        select(PasswordRecoveryToken).where(
            PasswordRecoveryToken.token_hash == hash_one_time_token(body.token),
            PasswordRecoveryToken.consumed_at.is_(None),
            PasswordRecoveryToken.expires_at > now,
        )
    )
    if recovery is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="重置链接无效或已过期")
    actor = db.get(User, recovery.user_id)
    if actor is None or not actor.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="重置链接无效或已过期")
    actor.password_hash = hash_password(body.new_password)
    actor.password_changed_at = now
    recovery.consumed_at = now
    db.commit()
    return MessageOut(message="密码已重置，请使用新密码登录")
