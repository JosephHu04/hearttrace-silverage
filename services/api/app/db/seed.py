from datetime import timedelta

from sqlalchemy.orm import Session

from app.db.models import (
    DailyInsight,
    DeviceElderBinding,
    ElderProfile,
    FamilyElderGrant,
    RiskEvent,
    RiskEvidence,
    User,
    utc_now,
)


def add_missing(db: Session, rows: list[object]) -> None:
    for row in rows:
        identity = tuple(getattr(row, column.name) for column in row.__table__.primary_key.columns)
        key = identity[0] if len(identity) == 1 else identity
        if db.get(type(row), key) is None:
            db.add(row)


def seed_demo_data(db: Session) -> None:
    now = utc_now()
    add_missing(
        db,
        [
            User(id="staff-admin-001", display_name="周老师", role="admin"),
            User(id="staff-professional-001", display_name="许老师", role="professional"),
            User(id="family-demo-001", display_name="林女士", role="family"),
            User(id="family-demo-002", display_name="王先生", role="family"),
            User(id="family-no-access-001", display_name="无授权测试账号", role="family"),
            User(id="elder-demo-001", display_name="陈奶奶", role="elder"),
            User(id="elder-demo-002", display_name="李爷爷", role="elder"),
            User(id="device-demo-001", display_name="陈奶奶客厅求助键", role="device_operator"),
        ],
    )
    db.flush()
    add_missing(
        db,
        [
            ElderProfile(user_id="elder-demo-001", age=82),
            ElderProfile(user_id="elder-demo-002", age=76),
            FamilyElderGrant(family_id="family-demo-001", elder_id="elder-demo-001", scopes=["daily_summary", "care_actions"]),
            FamilyElderGrant(family_id="family-demo-002", elder_id="elder-demo-002", scopes=["daily_summary", "care_actions"]),
            DeviceElderBinding(device_id="device-demo-001", elder_id="elder-demo-001"),
        ],
    )
    add_missing(
        db,
        [
            DailyInsight(
                id="insight-demo-001", elder_id="elder-demo-001", level="yellow", label="需要轻度关怀",
                headline="陈奶奶今天更适合收到一句不着急的问候。",
                summary="系统观察到她昨晚提到睡眠不太踏实；今天的交流中也出现了想家人的话题。没有发现紧急安全信号。",
                score=72, baseline_delta=-6,
                topics=[
                    {"name": "睡眠与作息", "note": "轻度关注", "tone": "lavender"},
                    {"name": "想念家人", "note": "建议联系", "tone": "peach"},
                    {"name": "午后晒太阳", "note": "正向事件", "tone": "mint"},
                ],
                has_active_emergency=False, safety_message="暂无紧急安全事件", created_at=now,
            ),
            DailyInsight(
                id="insight-demo-002", elder_id="elder-demo-002", level="green", label="状态平稳",
                headline="李爷爷今天精神不错，可以分享一些日常趣事。",
                summary="今日作息和交流频率接近个人基线，出现了散步与下棋等积极主题。没有发现紧急安全信号。",
                score=84, baseline_delta=2,
                topics=[
                    {"name": "公园散步", "note": "正向事件", "tone": "mint"},
                    {"name": "和老友下棋", "note": "保持联系", "tone": "lavender"},
                    {"name": "晚间作息", "note": "状态稳定", "tone": "mint"},
                ],
                has_active_emergency=False, safety_message="暂无紧急安全事件", created_at=now,
            ),
        ],
    )
    add_missing(
        db,
        [
            RiskEvent(
                id="risk-demo-001", elder_id="elder-demo-001", level="orange", status="new",
                title="连续低落并伴随睡眠变化",
                summary="规则、个人趋势与量表共同提示需要人工复核。该结论为关怀支持，不是疾病诊断。",
                model_version="analysis-agent-demo-1", rule_version="risk-rules-demo-1",
                sla_due_at=now + timedelta(hours=2), created_at=now, updated_at=now,
            ),
            RiskEvent(
                id="risk-demo-002", elder_id="elder-demo-002", level="green", status="new",
                title="日常状态平稳", summary="个人趋势接近基线，仅用于多账号联调，不表示疾病诊断。",
                model_version="analysis-agent-demo-1", rule_version="risk-rules-demo-1",
                sla_due_at=now + timedelta(hours=24), created_at=now, updated_at=now,
            ),
        ],
    )
    db.flush()
    add_missing(
        db,
        [
            RiskEvidence(id="evidence-demo-trend", risk_event_id="risk-demo-001", source_type="trend", label="个人趋势", detail="近三日心境指标持续低于本人近七日基线。", evidence_ref="daily-insight-demo-20260910", recorded_at=now),
            RiskEvidence(id="evidence-demo-screening", risk_event_id="risk-demo-001", source_type="screening", label="标准量表", detail="最近一次固定量表结果达到人工关注阈值。", evidence_ref="screening-demo-001", recorded_at=now),
            RiskEvidence(id="evidence-demo-model", risk_event_id="risk-demo-001", source_type="model_signal", label="分析 Agent 候选信号", detail="授权摘要中持续出现睡眠和孤独主题；模型信号不单独决定风险等级。", evidence_ref="message-summary-demo-001", recorded_at=now),
            RiskEvidence(id="evidence-demo-green", risk_event_id="risk-demo-002", source_type="trend", label="个人趋势", detail="今日作息与交流频率接近个人近七日基线。", evidence_ref="daily-insight-demo-002", recorded_at=now),
        ],
    )
    db.commit()
