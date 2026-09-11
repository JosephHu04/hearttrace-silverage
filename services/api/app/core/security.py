from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import os

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


def hash_password(password: str) -> str:
    """Use a portable stdlib password hash until the auth service is extracted."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return "pbkdf2_sha256$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, salt_encoded, digest_encoded = encoded.split("$", 2)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_encoded.encode())
        expected = base64.urlsafe_b64decode(digest_encoded.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def hash_one_time_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
