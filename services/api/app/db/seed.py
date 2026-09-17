from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import (
    DailyInsight,
    DeviceElderBinding,
    ElderProfile,
    FamilyCarePlanItem,
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
            User(id="staff-admin-001", display_name="周老师", role="admin", login_identifier="admin.demo@hearttrace.local", password_hash=hash_password("AdminDemo2026!")),
            User(id="staff-professional-001", display_name="许老师", role="professional"),
            User(id="family-demo-001", display_name="林女士", role="family", login_identifier="lin.demo@hearttrace.local", password_hash=hash_password("FamilyDemo2026!")),
            User(id="family-demo-002", display_name="王先生", role="family", login_identifier="wang.demo@hearttrace.local", password_hash=hash_password("FamilyDemo2026!")),
            User(id="family-no-access-001", display_name="无授权测试账号", role="family", login_identifier="noaccess.demo@hearttrace.local", password_hash=hash_password("NoAccessDemo2026!")),
            User(id="elder-demo-001", display_name="陈奶奶", role="elder"),
            User(id="elder-demo-002", display_name="李爷爷", role="elder"),
            User(id="device-demo-001", display_name="陈奶奶客厅求助键", role="device_operator"),
        ],
    )
    db.flush()
    for actor_id, identifier, password in [
        ("staff-admin-001", "admin.demo@hearttrace.local", "AdminDemo2026!"),
        ("elder-demo-001", "chen.demo@hearttrace.local", "ElderDemo2026!"),
        ("elder-demo-002", "li.demo@hearttrace.local", "ElderDemo2026!"),
        ("family-demo-001", "lin.demo@hearttrace.local", "FamilyDemo2026!"),
        ("family-demo-002", "wang.demo@hearttrace.local", "FamilyDemo2026!"),
        ("family-no-access-001", "noaccess.demo@hearttrace.local", "NoAccessDemo2026!"),
    ]:
        actor = db.get(User, actor_id)
        if actor is not None:
            if actor.login_identifier is None:
                actor.login_identifier = identifier
            if actor.password_hash is None:
                actor.password_hash = hash_password(password)
    add_missing(
        db,
        [
            ElderProfile(user_id="elder-demo-001", age=82),
            ElderProfile(user_id="elder-demo-002", age=76),
            FamilyElderGrant(family_id="family-demo-001", elder_id="elder-demo-001", scopes=["daily_summary", "care_actions"], relationship="女儿", consent_version="demo-consent-v1", created_by="staff-admin-001", updated_by="staff-admin-001", updated_at=now),
            FamilyElderGrant(family_id="family-demo-002", elder_id="elder-demo-002", scopes=["daily_summary", "care_actions"], relationship="儿子", consent_version="demo-consent-v1", created_by="staff-admin-001", updated_by="staff-admin-001", updated_at=now),
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
                score=None, baseline_delta=None,
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
                score=None, baseline_delta=None,
                topics=[
                    {"name": "公园散步", "note": "正向事件", "tone": "mint"},
                    {"name": "和老友下棋", "note": "保持联系", "tone": "lavender"},
                    {"name": "晚间作息", "note": "状态稳定", "tone": "mint"},
                ],
                has_active_emergency=False, safety_message="暂无紧急安全事件", created_at=now,
            ),
            DailyInsight(
                id="insight-demo-001-d1", elder_id="elder-demo-001", level="yellow", label="需要轻度关怀",
                headline="陈奶奶昨天的交流较为平稳。", summary="仅供趋势联调的历史结构化摘要。",
                score=None, baseline_delta=None, topics=[], has_active_emergency=False,
                safety_message="暂无紧急安全事件", created_at=now - timedelta(days=1),
            ),
            DailyInsight(
                id="insight-demo-001-d2", elder_id="elder-demo-001", level="green", label="状态平稳",
                headline="陈奶奶前天状态平稳。", summary="仅供趋势联调的历史结构化摘要。",
                score=None, baseline_delta=None, topics=[], has_active_emergency=False,
                safety_message="暂无紧急安全事件", created_at=now - timedelta(days=2),
            ),
            DailyInsight(
                id="insight-demo-001-d3", elder_id="elder-demo-001", level="yellow", label="需要轻度关怀",
                headline="陈奶奶三天前需要温和关注。", summary="仅供趋势联调的历史结构化摘要。",
                score=None, baseline_delta=None, topics=[], has_active_emergency=False,
                safety_message="暂无紧急安全事件", created_at=now - timedelta(days=3),
            ),
            DailyInsight(
                id="insight-demo-001-d4", elder_id="elder-demo-001", level="green", label="状态平稳",
                headline="陈奶奶四天前状态平稳。", summary="仅供趋势联调的历史结构化摘要。",
                score=None, baseline_delta=None, topics=[], has_active_emergency=False,
                safety_message="暂无紧急安全事件", created_at=now - timedelta(days=4),
            ),
            DailyInsight(
                id="insight-demo-001-d5", elder_id="elder-demo-001", level="green", label="状态平稳",
                headline="陈奶奶五天前状态平稳。", summary="仅供趋势联调的历史结构化摘要。",
                score=None, baseline_delta=None, topics=[], has_active_emergency=False,
                safety_message="暂无紧急安全事件", created_at=now - timedelta(days=5),
            ),
            DailyInsight(
                id="insight-demo-001-d6", elder_id="elder-demo-001", level="yellow", label="需要轻度关怀",
                headline="陈奶奶六天前略有波动。", summary="仅供趋势联调的历史结构化摘要。",
                score=None, baseline_delta=None, topics=[], has_active_emergency=False,
                safety_message="暂无紧急安全事件", created_at=now - timedelta(days=6),
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
    add_missing(
        db,
        [
            FamilyCarePlanItem(
                id="care-plan-demo-001", family_id="family-demo-001", elder_id="elder-demo-001",
                title="发一条轻松的早安语音", scheduled_for=now,
            ),
            FamilyCarePlanItem(
                id="care-plan-demo-002", family_id="family-demo-001", elder_id="elder-demo-001",
                title="询问是否愿意在今晚视频聊天", scheduled_for=now + timedelta(hours=8),
            ),
            FamilyCarePlanItem(
                id="care-plan-demo-003", family_id="family-demo-001", elder_id="elder-demo-001",
                title="与家人协调周末探望", scheduled_for=now + timedelta(days=3),
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
