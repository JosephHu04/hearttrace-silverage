from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def add_audit_log(
    db: Session,
    *,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    metadata: Optional[dict[str, object]] = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=metadata or {},
    )
    db.add(entry)
    return entry
