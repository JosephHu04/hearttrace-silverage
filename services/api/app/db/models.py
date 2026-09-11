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

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(32), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
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
