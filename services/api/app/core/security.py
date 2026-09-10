from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError

from app.core.config import get_settings


def create_access_token(*, actor_id: str, role: str) -> tuple[str, datetime]:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_exp_minutes)
    token = jwt.encode(
        {"sub": actor_id, "role": role, "exp": expires_at},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at


def decode_access_token(token: str) -> dict[str, object]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as exc:
        raise ValueError("invalid token") from exc
