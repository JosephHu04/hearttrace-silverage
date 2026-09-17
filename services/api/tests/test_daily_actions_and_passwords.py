from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import func, select, update

from app.db.models import AuditLog, FamilyActionRecord, FamilyElderGrant, RiskEvent
from app.db.session import SessionLocal, engine
from app.routers import auth


def test_daily_actions_work_without_open_risk_and_are_idempotent(client, family_headers, admin_headers):
    with SessionLocal() as db:
        db.execute(update(RiskEvent).where(RiskEvent.elder_id == "elder-demo-001").values(status="closed"))
        db.commit()
    assert client.get("/api/family/elders/elder-demo-001/today", headers=family_headers).json()["riskEventId"] is None
    path = "/api/family/elders/elder-demo-001/actions"
    for action in ("contacted", "video_planned"):
        body = {"requestId": f"daily-{action}", "action": action}
        response = client.post(path, headers=family_headers, json=body)
        assert response.status_code == 200 and response.json()["duplicate"] is False
        replay = client.post(path, headers=family_headers, json=body)
        assert replay.status_code == 200 and replay.json()["duplicate"] is True
    today = client.get("/api/family/elders/elder-demo-001/today", headers=family_headers).json()
    assert len(today["recentActions"]) == 2
    with SessionLocal() as db:
        rows = db.scalars(select(FamilyActionRecord)).all()
        assert len(rows) == 2 and all(row.risk_event_id is None and row.elder_id == "elder-demo-001" for row in rows)
        assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "family.contacted")) == 1
    audit = client.get("/api/admin/audit-logs?targetType=elder&targetId=elder-demo-001", headers=admin_headers).json()
    assert {"family.contacted", "family.video_planned"}.issubset({row["action"] for row in audit["items"]})
    assert client.post(path, headers=family_headers, json={"requestId": "daily-contacted", "action": "video_planned"}).status_code == 409


def test_daily_actions_deny_wrong_owner_scope_and_revoked_replays(client, family_headers, no_access_family_headers):
    path = "/api/family/elders/elder-demo-001/actions"
    body = {"requestId": "daily-revoked", "action": "contacted"}
    assert client.post(path, json=body).status_code == 401
    assert client.post(path, headers=no_access_family_headers, json=body).status_code == 403
    assert client.post("/api/family/elders/elder-demo-002/actions", headers=family_headers, json=body).status_code == 403
    assert client.post(path, headers=family_headers, json=body).status_code == 200
    assert client.post(path, headers=family_headers, json={"requestId": "daily-referral", "action": "referral_requested"}).status_code == 400
    with SessionLocal() as db:
        db.get(FamilyElderGrant, ("family-demo-001", "elder-demo-001")).scopes = ["daily_summary"]
        db.commit()
    assert client.post(path, headers=family_headers, json=body).status_code == 403
    assert client.get("/api/family/elders/elder-demo-001/today", headers=family_headers).json()["recentActions"] == []


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Requires independent PostgreSQL transactions")
def test_concurrent_daily_action_replays_produce_one_record(client, family_headers):
    def submit(_):
        return client.post("/api/family/elders/elder-demo-001/actions", headers=family_headers,
                           json={"requestId": "concurrent-daily", "action": "contacted"})
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(submit, range(2)))
    assert all(response.status_code == 200 for response in responses)
    assert sorted(response.json()["duplicate"] for response in responses) == [False, True]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(FamilyActionRecord)) == 1
        assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "family.contacted")) == 1


@pytest.mark.parametrize("identifier,password", [
    ("chen.demo@hearttrace.local", "ElderDemo2026!"),
    ("admin.demo@hearttrace.local", "AdminDemo2026!"),
])
def test_password_change_is_audited_and_revokes_all_old_tokens(client, identifier, password):
    credentials = {"loginIdentifier": identifier, "password": password}
    first = client.post("/api/auth/login", json=credentials).json()
    second = client.post("/api/auth/login", json=credentials).json()
    headers = {"Authorization": "Bearer " + first["accessToken"]}
    assert client.post("/api/auth/password/change", headers=headers, json={"currentPassword": "Incorrect2026!", "newPassword": "UpdatedSecure2026!"}).status_code == 400
    assert client.post("/api/auth/password/change", headers=headers, json={"currentPassword": password, "newPassword": password}).status_code == 400
    assert client.post("/api/auth/password/change", headers=headers, json={"currentPassword": password, "newPassword": "UpdatedSecure2026!"}).status_code == 200
    for old in (first, second):
        assert client.get("/api/notifications/me", headers={"Authorization": "Bearer " + old["accessToken"]}).status_code == 401
    assert client.post("/api/auth/login", json=credentials).status_code == 401
    assert client.post("/api/auth/login", json={**credentials, "password": "UpdatedSecure2026!"}).status_code == 200
    with SessionLocal() as db:
        logs = db.scalars(select(AuditLog).where(AuditLog.action == "account.password_changed")).all()
        assert len(logs) == 1 and logs[0].actor_id == first["actor"]["id"]
        assert logs[0].metadata_json == {"sessionsRevoked": True}


def test_elder_password_change_rejects_next_message_on_existing_socket(client, elder_headers):
    session = client.post("/api/conversations/sessions", headers=elder_headers, json={}).json()
    with client.websocket_connect("/api/realtime/conversation") as ws:
        ws.send_json({"type": "authenticate", "accessToken": elder_headers["Authorization"].removeprefix("Bearer "), "sessionId": session["id"]})
        assert ws.receive_json()["type"] == "ready"
        assert client.post("/api/auth/password/change", headers=elder_headers, json={"currentPassword": "ElderDemo2026!", "newPassword": "UpdatedSecure2026!"}).status_code == 200
        ws.send_json({"type": "message", "text": "这条消息不应被处理"})
        assert ws.receive_json()["type"] == "error"
        assert ws.receive()["code"] == 4401


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Requires independent PostgreSQL transactions")
def test_concurrent_password_changes_do_not_overwrite_each_other(client, elder_headers, monkeypatch):
    barrier = Barrier(2, timeout=10)
    original = auth.verify_password
    def synchronized_verify(password, encoded):
        result = original(password, encoded)
        barrier.wait()
        return result
    monkeypatch.setattr(auth, "verify_password", synchronized_verify)
    def change(index):
        return client.post("/api/auth/password/change", headers=elder_headers,
                           json={"currentPassword": "ElderDemo2026!", "newPassword": f"ChangedSecure2026-{index}"}).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(change, range(2)))
    assert sorted(responses) == [200, 409]
