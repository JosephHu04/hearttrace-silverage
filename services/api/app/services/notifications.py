from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
from typing import Protocol

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.db.models import FamilyElderGrant, NotificationRecord, OutboxEvent, User, utc_now
from app.services.audit import add_audit_log


NOTIFICATION_EVENT_TYPE = "notification.delivery.requested"
NOTIFICATION_SYSTEM_ACTOR_ID = "system-notification-worker"
MAX_DELIVERY_ATTEMPTS = 3


class NotificationDeliveryAdapter(Protocol):
    def deliver(self, notification: NotificationRecord, channels: list[str]) -> None: ...


class InAppNotificationAdapter:
    """The record itself is the in-app delivery; external adapters can replace this later."""

    def deliver(self, notification: NotificationRecord, channels: list[str]) -> None:
        if channels != ["in_app"]:
            raise ValueError("当前通知适配器只支持 in_app 渠道")
        del notification


@dataclass(frozen=True)
class NotificationDeliveryOutcome:
    event_id: str
    notification_id: str | None
    status: str
    error: str | None = None


def _dedupe_key(*parts: str) -> str:
    digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"notify:{digest}"


def create_notification(
    db: Session,
    *,
    recipient_id: str,
    category: str,
    title: str,
    body: str,
    target_type: str,
    target_id: str,
    event_key: str,
) -> NotificationRecord | None:
    recipient = db.get(User, recipient_id)
    if recipient is None or not recipient.is_active:
        return None
    dedupe_key = _dedupe_key(recipient_id, category, target_type, target_id, event_key)
    existing = db.scalar(select(NotificationRecord).where(NotificationRecord.dedupe_key == dedupe_key))
    if existing is not None:
        return existing

    notification = NotificationRecord(
        recipient_id=recipient_id,
        category=category,
        title=title[:120],
        body=body[:500],
        target_type=target_type,
        target_id=target_id,
        dedupe_key=dedupe_key,
    )
    db.add(notification)
    db.flush()
    db.add(
        OutboxEvent(
            event_type=NOTIFICATION_EVENT_TYPE,
            aggregate_type="notification",
            aggregate_id=notification.id,
            dedupe_key=f"notification-delivery:{notification.id}",
            payload_json={
                "notificationId": notification.id,
                "recipientId": recipient_id,
                "channels": ["in_app"],
            },
        )
    )
    return notification


def family_recipient_ids(db: Session, *, elder_id: str, required_scope: str) -> list[str]:
    grants = list(
        db.scalars(
            select(FamilyElderGrant).where(
                FamilyElderGrant.elder_id == elder_id,
                FamilyElderGrant.is_active.is_(True),
            )
        )
    )
    return [grant.family_id for grant in grants if required_scope in grant.scopes]


def staff_recipient_ids(db: Session) -> list[str]:
    return list(
        db.scalars(
            select(User.id).where(
                User.role.in_({"admin", "professional"}),
                User.is_active.is_(True),
            )
        )
    )


def notify_families(
    db: Session,
    *,
    elder_id: str,
    required_scope: str,
    category: str,
    title: str,
    body: str,
    target_type: str,
    target_id: str,
    event_key: str,
) -> list[NotificationRecord]:
    notifications = []
    for recipient_id in family_recipient_ids(db, elder_id=elder_id, required_scope=required_scope):
        notification = create_notification(
            db,
            recipient_id=recipient_id,
            category=category,
            title=title,
            body=body,
            target_type=target_type,
            target_id=target_id,
            event_key=event_key,
        )
        if notification is not None:
            notifications.append(notification)
    return notifications


def notify_staff(
    db: Session,
    *,
    category: str,
    title: str,
    body: str,
    target_type: str,
    target_id: str,
    event_key: str,
) -> list[NotificationRecord]:
    notifications = []
    for recipient_id in staff_recipient_ids(db):
        notification = create_notification(
            db,
            recipient_id=recipient_id,
            category=category,
            title=title,
            body=body,
            target_type=target_type,
            target_id=target_id,
            event_key=event_key,
        )
        if notification is not None:
            notifications.append(notification)
    return notifications


def _ensure_notification_system_actor(db: Session) -> User:
    actor = db.get(User, NOTIFICATION_SYSTEM_ACTOR_ID)
    if actor is None:
        actor = User(
            id=NOTIFICATION_SYSTEM_ACTOR_ID,
            display_name="通知投递 Worker",
            role="service",
            is_active=False,
        )
        db.add(actor)
        db.flush()
    return actor


def _claim_notification_event(db: Session) -> OutboxEvent | None:
    now = utc_now()
    event = db.scalar(
        select(OutboxEvent)
        .where(
            OutboxEvent.event_type == NOTIFICATION_EVENT_TYPE,
            OutboxEvent.attempts < MAX_DELIVERY_ATTEMPTS,
            OutboxEvent.available_at <= now,
            or_(
                OutboxEvent.status == "pending",
                and_(
                    OutboxEvent.status == "processing",
                    OutboxEvent.locked_at < now - timedelta(minutes=5),
                ),
            ),
        )
        .order_by(OutboxEvent.created_at.asc())
        .limit(1)
    )
    if event is None:
        return None
    result = db.execute(
        update(OutboxEvent)
        .where(
            OutboxEvent.id == event.id,
            OutboxEvent.status == event.status,
            OutboxEvent.attempts == event.attempts,
        )
        .values(status="processing", attempts=event.attempts + 1, locked_at=now, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        return None
    db.commit()
    db.refresh(event)
    return event


def process_next_notification_event(
    db: Session,
    *,
    adapter: NotificationDeliveryAdapter,
) -> NotificationDeliveryOutcome | None:
    event = _claim_notification_event(db)
    if event is None:
        return None
    notification_id = str(event.payload_json.get("notificationId", ""))
    try:
        notification = db.get(NotificationRecord, notification_id)
        channels = event.payload_json.get("channels")
        if notification is None:
            raise RuntimeError("通知投递任务引用的通知不存在")
        if event.payload_json.get("recipientId") != notification.recipient_id:
            raise RuntimeError("通知投递任务的接收人不一致")
        if not isinstance(channels, list) or any(not isinstance(item, str) for item in channels):
            raise RuntimeError("通知投递渠道不合法")
        adapter.deliver(notification, channels)

        actor = _ensure_notification_system_actor(db)
        event.status = "processed"
        event.processed_at = utc_now()
        event.locked_at = None
        event.last_error = None
        event.updated_at = utc_now()
        add_audit_log(
            db,
            actor_id=actor.id,
            action="notification.delivered",
            target_type="notification",
            target_id=notification.id,
            metadata={"recipientId": notification.recipient_id, "channels": channels},
        )
        db.commit()
        return NotificationDeliveryOutcome(
            event_id=event.id,
            notification_id=notification.id,
            status="processed",
        )
    except Exception as error:
        db.rollback()
        event = db.get(OutboxEvent, event.id)
        if event is None:
            return NotificationDeliveryOutcome(
                event_id="missing",
                notification_id=notification_id or None,
                status="missing",
                error=type(error).__name__,
            )
        message = f"{type(error).__name__}: {str(error)}"[:500]
        event.status = "failed" if event.attempts >= MAX_DELIVERY_ATTEMPTS else "pending"
        event.available_at = utc_now() + timedelta(seconds=min(60 * (2**event.attempts), 900))
        event.locked_at = None
        event.last_error = message
        event.updated_at = utc_now()
        if event.status == "failed":
            actor = _ensure_notification_system_actor(db)
            add_audit_log(
                db,
                actor_id=actor.id,
                action="notification.delivery_failed",
                target_type="outbox_event",
                target_id=event.id,
                metadata={"attempts": event.attempts, "errorType": type(error).__name__},
            )
        db.commit()
        return NotificationDeliveryOutcome(
            event_id=event.id,
            notification_id=notification_id or None,
            status=event.status,
            error=message,
        )
