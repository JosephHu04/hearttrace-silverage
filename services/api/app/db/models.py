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
