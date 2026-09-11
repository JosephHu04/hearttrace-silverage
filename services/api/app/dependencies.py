from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_db


bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[Session, Depends(get_db)]


def get_current_actor(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少访问令牌")

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="访问令牌无效或已过期") from exc

    actor_id = payload.get("sub")
    if not isinstance(actor_id, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="访问令牌无效")

    actor = db.get(User, actor_id)
    if actor is None or not actor.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在或已停用")
    return actor


CurrentActor = Annotated[User, Depends(get_current_actor)]


def require_risk_staff(actor: CurrentActor) -> User:
    if actor.role not in {"admin", "professional"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前角色无权访问风险复核")
    return actor


RiskStaff = Annotated[User, Depends(require_risk_staff)]


def require_family(actor: CurrentActor) -> User:
    if actor.role != "family":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前角色不是家属账号")
    return actor


FamilyActor = Annotated[User, Depends(require_family)]
