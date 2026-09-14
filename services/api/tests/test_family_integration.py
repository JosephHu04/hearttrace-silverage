from uuid import uuid4

from fastapi.testclient import TestClient


def test_seeded_family_account_can_use_the_normal_password_login(client: TestClient):
    response = client.post(
        "/api/auth/login",
        json={"loginIdentifier": "lin.demo@hearttrace.local", "password": "FamilyDemo2026!"},
    )
    assert response.status_code == 200
    assert response.json()["actor"] == {"id": "family-demo-001", "displayName": "林女士", "role": "family"}


def test_family_can_list_only_authorized_elders(client: TestClient, family_headers: dict[str, str]):
    response = client.get("/api/family/me/elders", headers=family_headers)
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"id": "elder-demo-001", "name": "陈奶奶", "age": 82, "authorizationStatus": "active"}
        ]
    }


def test_family_today_is_structured_and_excludes_private_content(
    client: TestClient, family_headers: dict[str, str]
):
    response = client.get("/api/family/elders/elder-demo-001/today", headers=family_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["elder"]["name"] == "陈奶奶"
    assert body["riskEventId"] == "risk-demo-001"
    assert body["status"]["level"] == "yellow"
    assert body["access"] == {"scopes": ["daily_summary", "care_actions"], "careActionsAllowed": True}
    assert body["recentActions"] == []
    assert "messageContent" not in body
    assert "transcript" not in body


def test_family_cannot_read_another_elders_summary(
    client: TestClient, family_headers: dict[str, str]
):
    response = client.get("/api/family/elders/elder-demo-002/today", headers=family_headers)
    assert response.status_code == 403


def test_no_access_account_sees_no_elders(
    client: TestClient, no_access_family_headers: dict[str, str]
):
    response = client.get("/api/family/me/elders", headers=no_access_family_headers)
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_family_action_is_authorized_idempotent_and_audited(
    client: TestClient, family_headers: dict[str, str], admin_headers: dict[str, str]
):
    request_id = str(uuid4())
    payload = {"requestId": request_id, "action": "contacted"}
    response = client.post("/api/family/risk-events/risk-demo-001/actions", headers=family_headers, json=payload)
    assert response.status_code == 200
    assert response.json()["duplicate"] is False

    duplicate = client.post("/api/family/risk-events/risk-demo-001/actions", headers=family_headers, json=payload)
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True

    audit = client.get(
        "/api/admin/audit-logs?targetType=risk_event&targetId=risk-demo-001",
        headers=admin_headers,
    )
    assert any(item["action"] == "family.contacted" for item in audit.json()["items"])

    today = client.get("/api/family/elders/elder-demo-001/today", headers=family_headers)
    assert today.status_code == 200
    assert today.json()["recentActions"][0]["action"] == "contacted"


def test_family_cannot_act_on_another_elders_event(
    client: TestClient, family_headers: dict[str, str]
):
    response = client.post(
        "/api/family/risk-events/risk-demo-002/actions",
        headers=family_headers,
        json={"requestId": str(uuid4()), "action": "contacted"},
    )
    assert response.status_code == 403


def test_family_trend_returns_only_authorized_daily_points_and_is_audited(
    client: TestClient, family_headers: dict[str, str], admin_headers: dict[str, str]
):
    response = client.get("/api/family/elders/elder-demo-001/trend?days=7", headers=family_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["periodDays"] == 7
    assert len(body["items"]) == 7
    assert {"recordedAt", "score", "level", "label"} == set(body["items"][0])
    assert all("summary" not in item and "transcript" not in item for item in body["items"])

    denied = client.get("/api/family/elders/elder-demo-002/trend?days=7", headers=family_headers)
    assert denied.status_code == 403

    audit = client.get(
        "/api/admin/audit-logs?targetType=elder&targetId=elder-demo-001",
        headers=admin_headers,
    )
    assert any(item["action"] == "family.trend_viewed" for item in audit.json()["items"])


def test_family_plan_is_private_to_family_and_completion_is_idempotent(
    client: TestClient, family_headers: dict[str, str], no_access_family_headers: dict[str, str], admin_headers: dict[str, str]
):
    created = client.post(
        "/api/family/elders/elder-demo-001/care-plan",
        headers=family_headers,
        json={"title": "周末和陈奶奶一起整理相册"},
    )
    assert created.status_code == 201
    item = created.json()
    assert item["title"] == "周末和陈奶奶一起整理相册"
    assert item["completedAt"] is None

    plan = client.get("/api/family/elders/elder-demo-001/care-plan", headers=family_headers)
    assert plan.status_code == 200
    assert any(row["id"] == item["id"] for row in plan.json())

    denied = client.get("/api/family/elders/elder-demo-001/care-plan", headers=no_access_family_headers)
    assert denied.status_code == 403

    completed = client.post(
        f"/api/family/elders/elder-demo-001/care-plan/{item['id']}/complete",
        headers=family_headers,
    )
    assert completed.status_code == 200
    assert completed.json()["completedAt"] is not None

    duplicate = client.post(
        f"/api/family/elders/elder-demo-001/care-plan/{item['id']}/complete",
        headers=family_headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["completedAt"] == completed.json()["completedAt"]

    audit = client.get(
        f"/api/admin/audit-logs?targetType=family_care_plan_item&targetId={item['id']}",
        headers=admin_headers,
    )
    actions = [row["action"] for row in audit.json()["items"]]
    assert "family.care_plan_created" in actions
    assert "family.care_plan_completed" in actions
