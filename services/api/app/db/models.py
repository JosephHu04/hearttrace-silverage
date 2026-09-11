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


class FamilyElderGrant(Base):
    __tablename__ = "family_elder_grants"

    family_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    elder_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DeviceElderBinding(Base):
    __tablename__ = "device_elder_bindings"

    device_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    elder_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DailyInsight(Base):
    __tablename__ = "daily_insights"
    __table_args__ = (Index("ix_daily_insights_elder_time", "elder_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    elder_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
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
    __table_args__ = (Index("ix_risk_events_queue", "level", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    elder_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
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
