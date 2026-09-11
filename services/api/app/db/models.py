from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def uuid_string() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("uq_users_login_identifier", "login_identifier", unique=True),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(32), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    login_identifier: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RegistrationApplication(Base):
    __tablename__ = "registration_applications"
    __table_args__ = (
        Index("ix_registration_applications_queue", "status", "created_at"),
        Index("ix_registration_applications_login_identifier", "login_identifier", unique=True),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    display_name: Mapped[str] = mapped_column(String(100))
    login_identifier: Mapped[str] = mapped_column(String(120))
    relationship: Mapped[str] = mapped_column(String(80))
    elder_name: Mapped[str] = mapped_column(String(100))
    elder_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    consent_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PasswordRecoveryToken(Base):
    __tablename__ = "password_recovery_tokens"
    __table_args__ = (Index("ix_password_recovery_tokens_lookup", "token_hash", "expires_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ElderProfile(Base):
    __tablename__ = "elder_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    age: Mapped[int] = mapped_column(Integer)


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"
    __table_args__ = (Index("ix_conversation_sessions_elder_time", "elder_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    elder_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    save_messages: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_analysis: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (Index("ix_conversation_messages_session_time", "session_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    session_id: Mapped[str] = mapped_column(ForeignKey("conversation_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    processing: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_delivery", "event_type", "status", "available_at"),
        Index("uq_outbox_events_dedupe_key", "dedupe_key", unique=True),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    aggregate_type: Mapped[str] = mapped_column(String(40))
    aggregate_id: Mapped[str] = mapped_column(String(64))
    dedupe_key: Mapped[str] = mapped_column(String(160))
    payload_json: Mapped[dict[str, object]] = mapped_column("payload", JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ConversationAnalysis(Base):
    __tablename__ = "conversation_analyses"
    __table_args__ = (
        Index("ix_conversation_analyses_elder_time", "elder_id", "created_at"),
        Index("uq_conversation_analyses_source_message", "source_message_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    session_id: Mapped[str] = mapped_column(ForeignKey("conversation_sessions.id"), index=True)
    source_message_id: Mapped[str] = mapped_column(ForeignKey("conversation_messages.id"))
    elder_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    candidate_signals: Mapped[list[str]] = mapped_column(JSON, default=list)
    urgent_safety_check: Mapped[bool] = mapped_column(Boolean, default=False)
    recommended_next_step: Mapped[str] = mapped_column(String(40))
    family_summary: Mapped[str] = mapped_column(String(300))
    evidence_message_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_version: Mapped[str] = mapped_column(String(80))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class NotificationRecord(Base):
    __tablename__ = "notification_records"
    __table_args__ = (
        Index("ix_notification_records_recipient_time", "recipient_id", "created_at"),
        Index("ix_notification_records_recipient_unread", "recipient_id", "is_read", "created_at"),
        Index("uq_notification_records_dedupe_key", "dedupe_key", unique=True),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    recipient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(500))
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(64))
    dedupe_key: Mapped[str] = mapped_column(String(80))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FamilyElderGrant(Base):
    __tablename__ = "family_elder_grants"

    family_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    elder_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    relationship: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    consent_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    revoked_by: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class DeviceElderBinding(Base):
    __tablename__ = "device_elder_bindings"

    device_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    elder_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DailyInsight(Base):
    __tablename__ = "daily_insights"
    __table_args__ = (
        Index("ix_daily_insights_elder_time", "elder_id", "created_at"),
        Index("uq_daily_insights_source_analysis", "source_analysis_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    elder_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source_analysis_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("conversation_analyses.id"), nullable=True
    )
    level: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(100))
    headline: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer)
    baseline_delta: Mapped[int] = mapped_column(Integer)
    topics: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    has_active_emergency: Mapped[bool] = mapped_column(Boolean, default=False)
    safety_message: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RiskEvent(Base):
    __tablename__ = "risk_events"
    __table_args__ = (
        Index("ix_risk_events_queue", "level", "status", "created_at"),
        Index("uq_risk_events_source_analysis", "source_analysis_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    elder_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source_analysis_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("conversation_analyses.id"), nullable=True
    )
    level: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    model_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rule_version: Mapped[str] = mapped_column(String(64))
    assignee_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    sla_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class RiskEvidence(Base):
    __tablename__ = "risk_evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    risk_event_id: Mapped[str] = mapped_column(ForeignKey("risk_events.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(Text)
    evidence_ref: Mapped[str] = mapped_column(String(128))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RiskAction(Base):
    __tablename__ = "risk_actions"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_risk_actions_request_id"),
        Index("ix_risk_actions_event_time", "risk_event_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    request_id: Mapped[str] = mapped_column(String(100))
    risk_event_id: Mapped[str] = mapped_column(ForeignKey("risk_events.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(32))
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    from_status: Mapped[str] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    event_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FamilyActionRecord(Base):
    __tablename__ = "family_action_records"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_family_action_records_request_id"),
        Index("ix_family_action_event_time", "risk_event_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    request_id: Mapped[str] = mapped_column(String(100))
    risk_event_id: Mapped[str] = mapped_column(ForeignKey("risk_events.id"))
    family_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EmergencyEvent(Base):
    __tablename__ = "emergency_events"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_emergency_events_request_id"),
        Index("ix_emergency_events_queue", "status", "created_at"),
        Index("ix_emergency_events_elder_time", "elder_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    request_id: Mapped[str] = mapped_column(String(100))
    elder_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    trigger_actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="open")
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class EmergencyAction(Base):
    __tablename__ = "emergency_actions"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_emergency_actions_request_id"),
        Index("ix_emergency_actions_event_time", "emergency_event_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    request_id: Mapped[str] = mapped_column(String(100))
    emergency_event_id: Mapped[str] = mapped_column(ForeignKey("emergency_events.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(24))
    note: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    from_status: Mapped[str] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    event_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_target_time", "target_type", "target_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
