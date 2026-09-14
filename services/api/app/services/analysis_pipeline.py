from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    ConversationAnalysis,
    ConversationMessage,
    ConversationSession,
    DailyInsight,
    OutboxEvent,
    RiskEvent,
    RiskEvidence,
    User,
    utc_now,
    uuid_string,
)
from app.services.audit import add_audit_log
from app.services.notifications import notify_families, notify_staff


ANALYSIS_EVENT_TYPE = "conversation.analysis.requested"
ANALYSIS_RULE_VERSION = "consented-analysis-routing-v1"
SYSTEM_ACTOR_ID = "system-analysis-worker"
MAX_ATTEMPTS = 3
LEASE_MINUTES = 5

SIGNAL_LABELS = {
    "loneliness": "孤独感候选信号",
    "sleep_change": "睡眠变化候选信号",
    "low_mood": "情绪低落候选信号",
    "anxiety": "焦虑感候选信号",
    "cognitive_concern": "认知担忧候选信号",
    "crisis_language": "危机语言候选信号",
}


class CandidateAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_signals: list[str] = Field(max_length=6)
    urgent_safety_check: bool
    recommended_next_step: str
    family_summary: str = Field(min_length=1, max_length=80)
    evidence_turn_indexes: list[int]

    @field_validator("candidate_signals")
    @classmethod
    def validate_signals(cls, value: list[str]) -> list[str]:
        if any(item not in SIGNAL_LABELS for item in value):
            raise ValueError("模型返回了不支持的候选信号")
        return list(dict.fromkeys(value))

    @field_validator("recommended_next_step")
    @classmethod
    def validate_next_step(cls, value: str) -> str:
        if value not in {"daily_care", "invite_screening", "human_follow_up", "emergency_workflow"}:
            raise ValueError("模型返回了不支持的下一步建议")
        return value

    @field_validator("family_summary")
    @classmethod
    def reject_diagnostic_language(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("家属摘要不能为空")
        prohibited = {"诊断", "抑郁症", "焦虑症", "痴呆症", "自杀风险"}
        if any(term in value for term in prohibited):
            raise ValueError("家属摘要不得包含诊断或风险结论")
        return value

    @model_validator(mode="after")
    def validate_emergency_route(self) -> "CandidateAnalysis":
        if self.urgent_safety_check and self.recommended_next_step != "emergency_workflow":
            raise ValueError("紧急安全确认必须进入 emergency_workflow")
        return self


class AnalysisAdapter(Protocol):
    def analyze(self, dialogue_turns: list[str]) -> tuple[dict[str, Any], dict[str, int]]: ...


@dataclass(frozen=True)
class AnalysisProcessOutcome:
    event_id: str
    status: str
    analysis_id: str | None = None
    risk_event_id: str | None = None
    error: str | None = None


def queue_conversation_analysis(
    db: Session,
    *,
    session: ConversationSession,
    source_message: ConversationMessage,
) -> OutboxEvent | None:
    """Queue a reference-only event; conversation text never enters the outbox."""
    if not session.save_messages or not session.allow_analysis or source_message.role != "assistant":
        return None

    dedupe_key = f"conversation-analysis:{source_message.id}"
    existing = db.scalar(select(OutboxEvent).where(OutboxEvent.dedupe_key == dedupe_key))
    if existing is not None:
        return existing

    event = OutboxEvent(
        event_type=ANALYSIS_EVENT_TYPE,
        aggregate_type="conversation_session",
        aggregate_id=session.id,
        dedupe_key=dedupe_key,
        payload_json={"sessionId": session.id, "sourceMessageId": source_message.id},
    )
    db.add(event)
    db.flush()
    add_audit_log(
        db,
        actor_id=session.elder_id,
        action="conversation.analysis_queued",
        target_type="conversation_session",
        target_id=session.id,
        metadata={"outboxEventId": event.id, "sourceMessageId": source_message.id},
    )
    return event


def _ensure_system_actor(db: Session) -> User:
    actor = db.get(User, SYSTEM_ACTOR_ID)
    if actor is None:
        actor = User(id=SYSTEM_ACTOR_ID, display_name="关怀分析 Worker", role="service", is_active=False)
        db.add(actor)
        db.flush()
    return actor


def _claim_next_event(db: Session) -> OutboxEvent | None:
    now = utc_now()
    lease_expired_at = now - timedelta(minutes=LEASE_MINUTES)
    event = db.scalar(
        select(OutboxEvent)
        .where(
            OutboxEvent.event_type == ANALYSIS_EVENT_TYPE,
            OutboxEvent.attempts < MAX_ATTEMPTS,
            OutboxEvent.available_at <= now,
            or_(
                OutboxEvent.status == "pending",
                and_(OutboxEvent.status == "processing", OutboxEvent.locked_at < lease_expired_at),
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


def _conversation_turns(
    db: Session,
    *,
    session_id: str,
    source_message_id: str,
) -> tuple[list[str], list[str]]:
    rows = list(
        db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        )
    )
    source_position = next((index for index, item in enumerate(rows) if item.id == source_message_id), None)
    if source_position is None:
        raise RuntimeError("分析任务引用的消息不存在")
    user_messages = [item for item in rows[: source_position + 1] if item.role == "user"][-16:]
    if not user_messages:
        raise RuntimeError("分析任务没有可用的老人消息")
    return [item.content for item in user_messages], [item.id for item in user_messages]


def _validate_output(raw: dict[str, Any], turn_count: int) -> CandidateAnalysis:
    analysis = CandidateAnalysis.model_validate(raw)
    if any(index < 0 or index >= turn_count for index in analysis.evidence_turn_indexes):
        raise ValueError("模型返回的证据下标越界")
    return analysis


def _review_level(analysis: CandidateAnalysis) -> str:
    if analysis.urgent_safety_check or analysis.recommended_next_step == "emergency_workflow":
        return "orange"
    return "yellow"


def _needs_human_review(analysis: CandidateAnalysis) -> bool:
    return analysis.urgent_safety_check or analysis.recommended_next_step in {
        "invite_screening",
        "human_follow_up",
        "emergency_workflow",
    }


def _attach_review_event(
    db: Session,
    *,
    session: ConversationSession,
    analysis_record: ConversationAnalysis,
    analysis: CandidateAnalysis,
) -> RiskEvent:
    mergeable_statuses = {"new", "assigned", "reviewing"}
    existing = db.scalar(
        select(RiskEvent)
        .join(ConversationAnalysis, RiskEvent.source_analysis_id == ConversationAnalysis.id)
        .where(
            ConversationAnalysis.session_id == session.id,
            RiskEvent.status.in_(mergeable_statuses),
        )
        .order_by(RiskEvent.created_at.desc())
        .limit(1)
    )
    detail = "候选信号：" + "、".join(SIGNAL_LABELS[item] for item in analysis.candidate_signals)
    detail += "。模型信号不单独构成诊断或最终风险结论。"
    if existing is not None:
        existing.source_analysis_id = analysis_record.id
        db.add(
            RiskEvidence(
                risk_event_id=existing.id,
                source_type="model_signal",
                label="分析 Agent 新增候选信号",
                detail=detail,
                evidence_ref=f"analysis:{analysis_record.id}",
            )
        )
        existing.updated_at = utc_now()
        notify_staff(
            db,
            category="risk_follow_up",
            title="风险事件新增候选证据",
            body="授权会话产生了新的结构化候选信号，请在复核时一并查看。",
            target_type="risk_event",
            target_id=existing.id,
            event_key=f"analysis:{analysis_record.id}",
        )
        return existing

    now = utc_now()
    level = _review_level(analysis)
    event = RiskEvent(
        id=f"risk-{uuid_string()}",
        elder_id=session.elder_id,
        source_analysis_id=analysis_record.id,
        level=level,
        status="new",
        title="授权对话产生待复核关怀信号",
        summary="关怀分析生成了结构化候选信号，需要结合个人趋势和量表人工复核；这不是疾病诊断。",
        model_version=analysis_record.model_version,
        rule_version=ANALYSIS_RULE_VERSION,
        sla_due_at=now + timedelta(minutes=30 if level == "orange" else 240),
        created_at=now,
        updated_at=now,
    )
    db.add(event)
    db.flush()
    db.add(
        RiskEvidence(
            risk_event_id=event.id,
            source_type="model_signal",
            label="分析 Agent 候选信号",
            detail=detail,
            evidence_ref=f"analysis:{analysis_record.id}",
        )
    )
    elder_name = db.scalar(select(User.display_name).where(User.id == session.elder_id)) or "老人"
    notify_staff(
        db,
        category="risk_follow_up",
        title="新的关怀分析待复核",
        body=f"{elder_name}的授权会话产生了结构化候选信号，请结合趋势和量表人工复核。",
        target_type="risk_event",
        target_id=event.id,
        event_key="created",
    )
    return event


def _record_failure(db: Session, event_id: str, error: Exception) -> AnalysisProcessOutcome:
    db.rollback()
    event = db.get(OutboxEvent, event_id)
    if event is None:
        return AnalysisProcessOutcome(event_id=event_id, status="missing", error=type(error).__name__)
    message = f"{type(error).__name__}: {str(error)}"[:500]
    event.status = "failed" if event.attempts >= MAX_ATTEMPTS else "pending"
    event.available_at = utc_now() + timedelta(seconds=min(60 * (2**event.attempts), 900))
    event.locked_at = None
    event.last_error = message
    event.updated_at = utc_now()
    if event.status == "failed":
        actor = _ensure_system_actor(db)
        add_audit_log(
            db,
            actor_id=actor.id,
            action="analysis.failed",
            target_type="outbox_event",
            target_id=event.id,
            metadata={"attempts": event.attempts, "errorType": type(error).__name__},
        )
    db.commit()
    return AnalysisProcessOutcome(event_id=event.id, status=event.status, error=message)


def process_next_analysis_event(
    db: Session,
    *,
    analyzer: AnalysisAdapter,
    model_version: str,
) -> AnalysisProcessOutcome | None:
    event = _claim_next_event(db)
    if event is None:
        return None

    try:
        session_id = str(event.payload_json.get("sessionId", ""))
        source_message_id = str(event.payload_json.get("sourceMessageId", ""))
        session = db.get(ConversationSession, session_id)
        if session is None:
            raise RuntimeError("分析任务引用的会话不存在")
        if not session.save_messages or not session.allow_analysis:
            actor = _ensure_system_actor(db)
            event.status = "processed"
            event.processed_at = utc_now()
            event.locked_at = None
            event.last_error = "consent_unavailable"
            add_audit_log(
                db,
                actor_id=actor.id,
                action="analysis.skipped",
                target_type="conversation_session",
                target_id=session.id,
                metadata={"reason": "consent_unavailable", "outboxEventId": event.id},
            )
            db.commit()
            return AnalysisProcessOutcome(event_id=event.id, status="skipped")

        existing = db.scalar(
            select(ConversationAnalysis).where(ConversationAnalysis.source_message_id == source_message_id)
        )
        if existing is not None:
            event.status = "processed"
            event.processed_at = utc_now()
            event.locked_at = None
            db.commit()
            return AnalysisProcessOutcome(event_id=event.id, status="processed", analysis_id=existing.id)

        turns, message_ids = _conversation_turns(
            db,
            session_id=session.id,
            source_message_id=source_message_id,
        )
        raw_analysis, usage = analyzer.analyze(turns)
        analysis = _validate_output(raw_analysis, len(turns))
        evidence_ids = [message_ids[index] for index in analysis.evidence_turn_indexes]
        analysis_record = ConversationAnalysis(
            session_id=session.id,
            source_message_id=source_message_id,
            elder_id=session.elder_id,
            candidate_signals=analysis.candidate_signals,
            urgent_safety_check=analysis.urgent_safety_check,
            recommended_next_step=analysis.recommended_next_step,
            family_summary=analysis.family_summary,
            evidence_message_ids=evidence_ids,
            model_version=model_version,
            prompt_tokens=max(0, int(usage.get("prompt_tokens", 0))),
            completion_tokens=max(0, int(usage.get("completion_tokens", 0))),
        )
        db.add(analysis_record)
        db.flush()

        risk_event = None
        if _needs_human_review(analysis):
            risk_event = _attach_review_event(
                db,
                session=session,
                analysis_record=analysis_record,
                analysis=analysis,
            )

        actor = _ensure_system_actor(db)
        event.status = "processed"
        event.processed_at = utc_now()
        event.locked_at = None
        event.last_error = None
        event.updated_at = utc_now()
        add_audit_log(
            db,
            actor_id=actor.id,
            action="analysis.completed",
            target_type="conversation_analysis",
            target_id=analysis_record.id,
            metadata={
                "elderId": session.elder_id,
                "candidateSignals": analysis.candidate_signals,
                "recommendedNextStep": analysis.recommended_next_step,
                "riskEventId": risk_event.id if risk_event is not None else None,
                "contentExposure": "structured_only",
            },
        )
        db.commit()
        return AnalysisProcessOutcome(
            event_id=event.id,
            status="processed",
            analysis_id=analysis_record.id,
            risk_event_id=risk_event.id if risk_event is not None else None,
        )
    except Exception as error:
        return _record_failure(db, event.id, error)


def publish_confirmed_analysis_summary(
    db: Session,
    *,
    risk_event: RiskEvent,
    actor_id: str,
) -> DailyInsight | None:
    if risk_event.source_analysis_id is None:
        return None
    existing = db.scalar(
        select(DailyInsight).where(DailyInsight.source_analysis_id == risk_event.source_analysis_id)
    )
    if existing is not None:
        return existing
    analysis = db.get(ConversationAnalysis, risk_event.source_analysis_id)
    if analysis is None:
        return None

    score_by_level = {"green": 82, "yellow": 72, "orange": 60, "red": 45}
    delta_by_level = {"green": 0, "yellow": -4, "orange": -8, "red": -12}
    label_by_level = {
        "green": "状态平稳",
        "yellow": "建议温和关怀",
        "orange": "建议尽快联系",
        "red": "需要立即确认安全",
    }
    topics = [
        {
            "name": SIGNAL_LABELS[signal].removesuffix("候选信号"),
            "note": "已由工作人员确认需要关注",
            "tone": "peach" if risk_event.level in {"orange", "red"} else "lavender",
        }
        for signal in analysis.candidate_signals[:3]
    ]
    insight = DailyInsight(
        elder_id=risk_event.elder_id,
        source_analysis_id=analysis.id,
        level=risk_event.level,
        label=label_by_level.get(risk_event.level, "建议保持关怀"),
        headline="今天适合多一份温和、直接的联系。",
        summary=analysis.family_summary,
        score=score_by_level.get(risk_event.level, 70),
        baseline_delta=delta_by_level.get(risk_event.level, -4),
        topics=topics,
        has_active_emergency=False,
        safety_message=(
            "工作人员已确认需要尽快联系老人；如无法确认安全，请使用紧急联络渠道。"
            if analysis.urgent_safety_check
            else "暂无紧急安全事件"
        ),
    )
    db.add(insight)
    db.flush()
    add_audit_log(
        db,
        actor_id=actor_id,
        action="analysis.summary_published",
        target_type="daily_insight",
        target_id=insight.id,
        metadata={
            "analysisId": analysis.id,
            "riskEventId": risk_event.id,
            "audience": "authorized_family",
            "contentExposure": "structured_only",
        },
    )
    elder_name = db.scalar(select(User.display_name).where(User.id == risk_event.elder_id)) or "老人"
    notify_families(
        db,
        elder_id=risk_event.elder_id,
        required_scope="daily_summary",
        category="analysis_summary",
        title="新的关怀摘要",
        body=f"{elder_name}有一条经工作人员确认的关怀摘要，请查看今日状态。",
        target_type="daily_insight",
        target_id=insight.id,
        event_key=f"analysis:{analysis.id}",
    )
    return insight
