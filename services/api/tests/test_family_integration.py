from uuid import uuid4

from fastapi.testclient import TestClient


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


def test_family_cannot_act_on_another_elders_event(
    client: TestClient, family_headers: dict[str, str]
):
    response = client.post(
        "/api/family/risk-events/risk-demo-002/actions",
        headers=family_headers,
        json={"requestId": str(uuid4()), "action": "contacted"},
    )
    assert response.status_code == 403
