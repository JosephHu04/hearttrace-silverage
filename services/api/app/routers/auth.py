from fastapi import APIRouter, HTTPException, status

from app.core.security import create_access_token
from app.db.models import User
from app.dependencies import DbSession
from app.schemas import ActorOut, DemoLoginRequest, TokenOut


router = APIRouter(prefix="/auth", tags=["auth"])


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
