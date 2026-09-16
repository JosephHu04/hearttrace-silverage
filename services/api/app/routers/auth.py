from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.security import create_access_token, hash_one_time_token, hash_password, verify_password
from app.db.models import PasswordRecoveryToken, RegistrationApplication, User, utc_now
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
    RegistrationApplicationStatusOut,
    RegistrationStatus,
    TokenOut,
)


router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


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
    if not settings.enable_demo_login:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="演示登录未启用")
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


@router.get("/registration-applications/{application_id}", response_model=RegistrationApplicationStatusOut)
def registration_application_status(application_id: str, db: DbSession) -> RegistrationApplicationStatusOut:
    application = db.get(RegistrationApplication, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该注册申请")
    return RegistrationApplicationStatusOut.model_validate(application)


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
    # Do not claim delivery or create unusable tokens until a real SMS/email
    # transport, rate limit and failure handling are implemented.
    del body, db
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="自助密码找回暂未开通，请联系管理员核验身份",
    )


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
    db.execute(
        update(PasswordRecoveryToken)
        .where(
            PasswordRecoveryToken.user_id == actor.id,
            PasswordRecoveryToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    db.commit()
    return MessageOut(message="密码已重置，请使用新密码登录")
