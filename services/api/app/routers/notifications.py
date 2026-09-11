from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.db.models import NotificationRecord, utc_now
from app.dependencies import CurrentActor, DbSession
from app.schemas import NotificationListOut, NotificationOut, NotificationReadResult
from app.services.audit import add_audit_log


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/me", response_model=NotificationListOut)
def my_notifications(
    db: DbSession,
    actor: CurrentActor,
    unread_only: bool = Query(default=False, alias="unreadOnly"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100, alias="perPage"),
) -> NotificationListOut:
    filters = [NotificationRecord.recipient_id == actor.id]
    if unread_only:
        filters.append(NotificationRecord.is_read.is_(False))
    total = db.scalar(select(func.count()).select_from(NotificationRecord).where(*filters)) or 0
    unread_count = db.scalar(
        select(func.count())
        .select_from(NotificationRecord)
        .where(
            NotificationRecord.recipient_id == actor.id,
            NotificationRecord.is_read.is_(False),
        )
    ) or 0
    rows = list(
        db.scalars(
            select(NotificationRecord)
            .where(*filters)
            .order_by(NotificationRecord.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    )
    return NotificationListOut(
        items=[NotificationOut.model_validate(item) for item in rows],
        unread_count=unread_count,
        page=page,
        per_page=per_page,
        total=total,
    )


@router.post("/{notification_id}/read", response_model=NotificationReadResult)
def mark_notification_read(
    notification_id: str,
    db: DbSession,
    actor: CurrentActor,
) -> NotificationReadResult:
    notification = db.get(NotificationRecord, notification_id)
    if notification is None or notification.recipient_id != actor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在")
    if notification.is_read:
        return NotificationReadResult(
            notification=NotificationOut.model_validate(notification),
            duplicate=True,
        )

    notification.is_read = True
    notification.read_at = utc_now()
    add_audit_log(
        db,
        actor_id=actor.id,
        action="notification.read",
        target_type="notification",
        target_id=notification.id,
        metadata={"category": notification.category, "targetType": notification.target_type},
    )
    db.commit()
    db.refresh(notification)
    return NotificationReadResult(notification=NotificationOut.model_validate(notification))
