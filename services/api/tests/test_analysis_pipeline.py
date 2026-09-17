from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import (
    ConversationAnalysis,
    ConversationSession,
    EmergencyEvent,
    OutboxEvent,
    RiskEvent,
    RiskEvidence,
)
from app.db.session import SessionLocal
from app.services.analysis_pipeline import SYSTEM_ACTOR_ID, process_next_analysis_event


class FakeAnalyzer:
    def __init__(self, output: dict[str, Any] | None = None) -> None:
        self.output = output or {
            "candidate_signals": ["low_mood", "sleep_change"],
            "urgent_safety_check": False,
            "recommended_next_step": "invite_screening",
            "family_summary": "今天情绪和睡眠有些变化，适合温和联系并询问是否愿意接受进一步关怀。",
            "evidence_turn_indexes": [0],
        }
        self.calls: list[list[str]] = []

    def analyze(self, dialogue_turns: list[str]) -> tuple[dict[str, Any], dict[str, int]]:
        self.calls.append(dialogue_turns)
        return self.output, {"prompt_tokens": 20, "completion_tokens": 10}


def test_new_family_registration_to_chat_summary_follow_up_and_revocation(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    elder_credentials = {"loginIdentifier": "elder-closure@example.test", "password": "ElderClosure2026!"}
    created_elder = client.post("/api/admin/elders", headers=admin_headers, json={
        **elder_credentials, "displayName": "新建老人", "age": 76,
    })
    assert created_elder.status_code == 201
    elder_id = created_elder.json()["id"]
    elder_login = client.post("/api/auth/login", json=elder_credentials)
    assert elder_login.status_code == 200 and elder_login.json()["actor"]["role"] == "elder"
    elder_headers = {"Authorization": f"Bearer {elder_login.json()['accessToken']}"}
    credentials = {"loginIdentifier": "closure@example.test", "password": "ClosureTest2026!"}
    submitted = client.post("/api/auth/registration-applications", json={
        **credentials,
        "displayName": "闭环测试家属",
        "relationship": "子女",
        "elderName": "新建老人",
        "consentVersion": "family-registration-v1",
    })
    assert submitted.status_code == 201
    assert client.post("/api/auth/login", json=credentials).status_code == 401
    approved = client.post(
        f"/api/admin/registration-applications/{submitted.json()['id']}/review",
        headers=admin_headers,
        json={"decision": "approved", "elderId": elder_id},
    )
    assert approved.status_code == 200
    login = client.post("/api/auth/login", json=credentials)
    assert login.status_code == 200
    family_id = login.json()["actor"]["id"]
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    empty = client.get(f"/api/family/elders/{elder_id}/today", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["status"]["summaryState"] == "empty"
    assert empty.json()["status"]["score"] is None
    assert client.get("/api/family/elders/elder-demo-002/today", headers=headers).status_code == 403

    # A newly provisioned elder completes an authorized chat. The analyzer is synthetic;
    # this verifies integration and persistence, not external-model accuracy.
    _complete_turn(client, elder_headers, save_messages=True, allow_analysis=True)
    analyzer = FakeAnalyzer()
    with SessionLocal() as db:
        outcome = process_next_analysis_event(db, analyzer=analyzer, model_version="closure-test-v1")
    assert outcome is not None and outcome.status == "processed"
    assert outcome.risk_event_id is not None
    risk_id = outcome.risk_event_id
    for version, action in enumerate(("claim", "begin_review", "request_action"), start=1):
        result = client.post(f"/api/admin/risk-events/{risk_id}/actions", headers=admin_headers, json={
            "requestId": f"closure-{action}", "action": action,
            "expectedVersion": version, "note": "合成测试：已完成人工复核。",
        })
        assert result.status_code == 200
    today = client.get(f"/api/family/elders/{elder_id}/today", headers=headers)
    assert today.status_code == 200
    assert today.json()["status"]["summary"] == analyzer.output["family_summary"]
    assert today.json()["status"]["score"] is None
    assert today.json()["status"]["summaryState"] == "ready"
    contacted = client.post(f"/api/family/risk-events/{risk_id}/actions", headers=headers, json={
        "requestId": "closure-contacted", "action": "contacted",
    })
    assert contacted.status_code == 200
    notifications = client.get("/api/notifications/me", headers=headers)
    assert notifications.status_code == 200
    assert "analysis_summary" in {item["category"] for item in notifications.json()["items"]}
    for action in ("family.today_viewed", "family.contacted"):
        audit = client.get(f"/api/admin/audit-logs?actorId={family_id}&action={action}", headers=admin_headers)
        assert audit.status_code == 200 and audit.json()["total"] >= 1
    revoked = client.post(f"/api/admin/family-grants/{family_id}/{elder_id}/actions", headers=admin_headers, json={
        "action": "revoke", "expectedVersion": 1, "note": "合成测试：撤回家属授权。",
    })
    assert revoked.status_code == 200
    assert client.get(f"/api/family/elders/{elder_id}/today", headers=headers).status_code == 403


def _token(headers: dict[str, str]) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


def _complete_turn(
    client: TestClient,
    elder_headers: dict[str, str],
    *,
    save_messages: bool,
    allow_analysis: bool,
    message: str = "这几天总觉得心情低落，晚上也睡不踏实。",
) -> str:
    response = client.post(
        "/api/conversations/sessions",
        headers=elder_headers,
        json={"saveMessages": save_messages, "allowAnalysis": allow_analysis},
    )
    assert response.status_code == 201
    session_id = response.json()["id"]
    with client.websocket_connect("/api/realtime/conversation") as websocket:
        websocket.send_json(
            {
                "type": "authenticate",
                "accessToken": _token(elder_headers),
                "sessionId": session_id,
            }
        )
        assert websocket.receive_json()["type"] == "ready"
        websocket.send_json({"type": "message", "text": message})
        while websocket.receive_json()["type"] not in {"done", "error"}:
            pass
    return session_id


def test_outbox_requires_both_storage_and_analysis_consent(
    client: TestClient,
    elder_headers: dict[str, str],
) -> None:
    _complete_turn(client, elder_headers, save_messages=True, allow_analysis=False)
    _complete_turn(client, elder_headers, save_messages=False, allow_analysis=True)
    consented_session_id = _complete_turn(
        client,
        elder_headers,
        save_messages=True,
        allow_analysis=True,
    )

    with SessionLocal() as db:
        events = list(db.scalars(select(OutboxEvent)))
        assert len(events) == 1
        assert events[0].aggregate_id == consented_session_id
        assert set(events[0].payload_json) == {"sessionId", "sourceMessageId"}
        assert "心情低落" not in str(events[0].payload_json)


def test_worker_creates_structured_review_and_human_confirmation_publishes_summary(
    client: TestClient,
    elder_headers: dict[str, str],
    admin_headers: dict[str, str],
    family_headers: dict[str, str],
) -> None:
    _complete_turn(client, elder_headers, save_messages=True, allow_analysis=True)
    analyzer = FakeAnalyzer()
    with SessionLocal() as db:
        outcome = process_next_analysis_event(db, analyzer=analyzer, model_version="fake-analysis-v1")
        assert outcome is not None
        assert outcome.status == "processed"
        assert outcome.analysis_id is not None
        assert outcome.risk_event_id is not None

        analysis = db.get(ConversationAnalysis, outcome.analysis_id)
        event = db.get(RiskEvent, outcome.risk_event_id)
        evidence = db.scalar(select(RiskEvidence).where(RiskEvidence.risk_event_id == outcome.risk_event_id))
        assert analysis is not None
        assert event is not None
        assert evidence is not None
        assert analysis.candidate_signals == ["low_mood", "sleep_change"]
        assert event.level == "yellow"
        assert event.status == "new"
        assert "心情低落" not in evidence.detail
        assert evidence.evidence_ref == f"analysis:{analysis.id}"
    assert analyzer.calls == [["这几天总觉得心情低落，晚上也睡不踏实。"]]

    system_login = client.post("/api/auth/demo-login", json={"actorId": SYSTEM_ACTOR_ID})
    assert system_login.status_code == 401

    detail = client.get(f"/api/admin/risk-events/{outcome.risk_event_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["evidence"][0]["sourceType"] == "model_signal"
    assert "这几天" not in str(detail.json())

    expected_version = 1
    for action, note in (("claim", None), ("begin_review", None), ("request_action", "已人工复核，建议家属温和联系并邀请筛查。")):
        response = client.post(
            f"/api/admin/risk-events/{outcome.risk_event_id}/actions",
            headers=admin_headers,
            json={
                "requestId": f"analysis-{action}-001",
                "action": action,
                "expectedVersion": expected_version,
                "note": note,
            },
        )
        assert response.status_code == 200
        expected_version += 1

    today = client.get("/api/family/elders/elder-demo-001/today", headers=family_headers)
    assert today.status_code == 200
    assert today.json()["status"]["summary"] == analyzer.output["family_summary"]
    assert today.json()["status"]["label"] == "建议温和关怀"

    audits = client.get(
        "/api/admin/audit-logs?action=analysis.summary_published",
        headers=admin_headers,
    )
    assert audits.status_code == 200
    assert audits.json()["total"] == 1
    assert audits.json()["items"][0]["metadata"]["contentExposure"] == "structured_only"


def test_worker_rechecks_consent_before_reading_messages(
    client: TestClient,
    elder_headers: dict[str, str],
) -> None:
    session_id = _complete_turn(client, elder_headers, save_messages=True, allow_analysis=True)
    analyzer = FakeAnalyzer()
    with SessionLocal() as db:
        session = db.get(ConversationSession, session_id)
        assert session is not None
        session.allow_analysis = False
        db.commit()

        outcome = process_next_analysis_event(db, analyzer=analyzer, model_version="fake-analysis-v1")
        assert outcome is not None
        assert outcome.status == "skipped"
        assert db.scalar(select(func.count()).select_from(ConversationAnalysis)) == 0
    assert analyzer.calls == []


def test_invalid_model_output_is_retried_without_persisting_analysis(
    client: TestClient,
    elder_headers: dict[str, str],
) -> None:
    _complete_turn(client, elder_headers, save_messages=True, allow_analysis=True)
    analyzer = FakeAnalyzer(
        {
            "candidate_signals": ["diagnosis"],
            "urgent_safety_check": False,
            "recommended_next_step": "daily_care",
            "family_summary": "无效输出",
            "evidence_turn_indexes": [0],
        }
    )
    with SessionLocal() as db:
        outcome = process_next_analysis_event(db, analyzer=analyzer, model_version="fake-analysis-v1")
        assert outcome is not None
        assert outcome.status == "pending"
        event = db.get(OutboxEvent, outcome.event_id)
        assert event is not None
        assert event.attempts == 1
        assert "ValidationError" in (event.last_error or "")
        assert db.scalar(select(func.count()).select_from(ConversationAnalysis)) == 0


def test_urgent_candidate_requests_fast_review_but_does_not_create_emergency(
    client: TestClient,
    elder_headers: dict[str, str],
) -> None:
    _complete_turn(
        client,
        elder_headers,
        save_messages=True,
        allow_analysis=True,
        message="这是合成的危机语言测试文本。",
    )
    analyzer = FakeAnalyzer(
        {
            "candidate_signals": ["crisis_language"],
            "urgent_safety_check": True,
            "recommended_next_step": "emergency_workflow",
            "family_summary": "工作人员需要尽快人工确认老人当前是否安全。",
            "evidence_turn_indexes": [0],
        }
    )
    with SessionLocal() as db:
        outcome = process_next_analysis_event(db, analyzer=analyzer, model_version="fake-analysis-v1")
        assert outcome is not None
        assert outcome.risk_event_id is not None
        risk_event = db.get(RiskEvent, outcome.risk_event_id)
        assert risk_event is not None
        assert risk_event.level == "orange"
        assert db.scalar(select(func.count()).select_from(EmergencyEvent)) == 0


def test_daily_care_can_publish_without_invented_scores(client, elder_headers, admin_headers, family_headers):
    _complete_turn(client, elder_headers, save_messages=True, allow_analysis=True)
    analyzer = FakeAnalyzer({
        "candidate_signals": [], "urgent_safety_check": False,
        "recommended_next_step": "daily_care", "family_summary": "今天聊了散步和日常生活，可以继续轻松问候。",
        "evidence_turn_indexes": [0],
    })
    with SessionLocal() as db:
        outcome = process_next_analysis_event(db, analyzer=analyzer, model_version="daily-test")
        assert outcome.status == "processed"
        assert db.get(RiskEvent, outcome.risk_event_id).level == "green"
    for version, action in enumerate(("claim", "begin_review", "resolve"), start=1):
        response = client.post(f"/api/admin/risk-events/{outcome.risk_event_id}/actions", headers=admin_headers,
                               json={"requestId": f"daily-{action}", "action": action, "expectedVersion": version, "note": "已核对，可发布日常摘要。"})
        assert response.status_code == 200
    today = client.get("/api/family/elders/elder-demo-001/today", headers=family_headers).json()
    assert today["status"]["summary"] == analyzer.output["family_summary"]
    assert today["status"]["score"] is None and today["status"]["baselineDelta"] is None
    assert today["status"]["summaryState"] == "ready"


def test_new_urgent_evidence_advances_version_and_never_downgrades(client, elder_headers, admin_headers):
    session_id = _complete_turn(client, elder_headers, save_messages=True, allow_analysis=True)
    with SessionLocal() as db:
        first = process_next_analysis_event(db, analyzer=FakeAnalyzer(), model_version="first")
    outputs = [
        {"candidate_signals": ["crisis_language"], "urgent_safety_check": True, "recommended_next_step": "emergency_workflow", "family_summary": "请工作人员尽快确认安全。", "evidence_turn_indexes": [0]},
        {"candidate_signals": [], "urgent_safety_check": False, "recommended_next_step": "daily_care", "family_summary": "新一轮聊天谈到日常生活。", "evidence_turn_indexes": [0]},
    ]
    urgent_analysis_id = None
    for index, output in enumerate(outputs, start=2):
        with client.websocket_connect("/api/realtime/conversation") as ws:
            ws.send_json({"type": "authenticate", "accessToken": _token(elder_headers), "sessionId": session_id})
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"type": "message", "text": "合成测试：我想再聊一会。"})
            while ws.receive_json()["type"] not in {"done", "error"}:
                pass
        with SessionLocal() as db:
            result = process_next_analysis_event(db, analyzer=FakeAnalyzer(output), model_version="new")
            assert result.risk_event_id == first.risk_event_id
            event = db.get(RiskEvent, first.risk_event_id)
            assert event.level == "orange" and event.version == index
            if index == 2:
                urgent_analysis_id = result.analysis_id
            assert event.source_analysis_id == urgent_analysis_id
    stale = client.post(f"/api/admin/risk-events/{first.risk_event_id}/actions", headers=admin_headers,
                        json={"requestId": "stale-evidence-claim", "action": "claim", "expectedVersion": 1})
    assert stale.status_code == 409


def test_withdrawn_analysis_cannot_be_published(client, elder_headers, admin_headers):
    session_id = _complete_turn(client, elder_headers, save_messages=True, allow_analysis=True)
    with SessionLocal() as db:
        outcome = process_next_analysis_event(db, analyzer=FakeAnalyzer(), model_version="withdraw-test")
    for version, action in enumerate(("claim", "begin_review"), start=1):
        assert client.post(f"/api/admin/risk-events/{outcome.risk_event_id}/actions", headers=admin_headers,
                           json={"requestId": f"withdraw-{action}", "action": action, "expectedVersion": version}).status_code == 200
    withdrawn = client.post(f"/api/conversations/sessions/{session_id}/revoke-analysis", headers=elder_headers)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["allowAnalysis"] is False and withdrawn.json()["saveMessages"] is False
    response = client.post(f"/api/admin/risk-events/{outcome.risk_event_id}/actions", headers=admin_headers,
                           json={"requestId": "withdraw-publish", "action": "request_action", "expectedVersion": 3, "note": "尝试发布。"})
    assert response.status_code == 409
    with SessionLocal() as db:
        assert db.get(RiskEvent, outcome.risk_event_id).status == "reviewing"


def test_consent_withdrawn_while_model_runs_discards_output(client, elder_headers):
    session_id = _complete_turn(client, elder_headers, save_messages=True, allow_analysis=True)
    class WithdrawingAnalyzer(FakeAnalyzer):
        def analyze(self, turns):
            assert client.post(f"/api/conversations/sessions/{session_id}/revoke-analysis", headers=elder_headers).status_code == 200
            return super().analyze(turns)
    with SessionLocal() as db:
        result = process_next_analysis_event(db, analyzer=WithdrawingAnalyzer(), model_version="withdraw-during-model")
        assert result.status == "skipped"
        assert db.scalar(select(func.count()).select_from(ConversationAnalysis)) == 0
