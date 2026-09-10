from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RiskEvent, RiskEvidence, User, utc_now


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)) is not None:
        return

    now = utc_now()
    db.add_all(
        [
            User(id="staff-admin-001", display_name="周老师", role="admin"),
            User(id="staff-professional-001", display_name="许老师", role="professional"),
            User(id="family-demo-001", display_name="林女士", role="family"),
            User(id="elder-demo-001", display_name="陈奶奶", role="elder"),
        ]
    )
    db.add(
        RiskEvent(
            id="risk-demo-001",
            elder_id="elder-demo-001",
            level="orange",
            status="new",
            title="连续低落并伴随睡眠变化",
            summary="规则、个人趋势与量表共同提示需要人工复核。该结论为关怀支持，不是疾病诊断。",
            model_version="analysis-agent-demo-1",
            rule_version="risk-rules-demo-1",
            sla_due_at=now + timedelta(hours=2),
            created_at=now,
            updated_at=now,
        )
    )
    db.add_all(
        [
            RiskEvidence(
                id="evidence-demo-trend",
                risk_event_id="risk-demo-001",
                source_type="trend",
                label="个人趋势",
                detail="近三日心境指标持续低于本人近七日基线。",
                evidence_ref="daily-insight-demo-20260910",
                recorded_at=now,
            ),
            RiskEvidence(
                id="evidence-demo-screening",
                risk_event_id="risk-demo-001",
                source_type="screening",
                label="标准量表",
                detail="最近一次固定量表结果达到人工关注阈值。",
                evidence_ref="screening-demo-001",
                recorded_at=now,
            ),
            RiskEvidence(
                id="evidence-demo-model",
                risk_event_id="risk-demo-001",
                source_type="model_signal",
                label="分析 Agent 候选信号",
                detail="授权摘要中持续出现睡眠和孤独主题；模型信号不单独决定风险等级。",
                evidence_ref="message-summary-demo-001",
                recorded_at=now,
            ),
        ]
    )
    db.commit()
