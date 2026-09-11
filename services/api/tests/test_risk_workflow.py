from __future__ import annotations

from typing import Optional
from uuid import uuid4

from fastapi.testclient import TestClient


def action_payload(action: str, version: int, note: Optional[str] = None, request_id: Optional[str] = None):
    return {
        "requestId": request_id or str(uuid4()),
        "action": action,
        "expectedVersion": version,
        "note": note,
    }


def test_health_check(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "core-api"}


def test_family_role_cannot_access_admin_queue(client: TestClient, family_headers: dict[str, str]):
    response = client.get("/api/admin/risk-events", headers=family_headers)
    assert response.status_code == 403


def test_risk_detail_returns_structured_evidence_and_audits_view(
    client: TestClient, admin_headers: dict[str, str]
):
    response = client.get("/api/admin/risk-events/risk-demo-001", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "new"
    assert {item["sourceType"] for item in body["evidence"]} == {"trend", "screening", "model_signal"}
    assert "messageContent" not in body

    audit_response = client.get(
        "/api/admin/audit-logs?targetType=risk_event&targetId=risk-demo-001",
        headers=admin_headers,
    )
    assert audit_response.status_code == 200
    assert any(item["action"] == "risk.viewed" for item in audit_response.json()["items"])


def test_workflow_is_versioned_idempotent_and_audited(client: TestClient, admin_headers: dict[str, str]):
    request_id = str(uuid4())
    claim = client.post(
        "/api/admin/risk-events/risk-demo-001/actions",
        headers=admin_headers,
        json=action_payload("claim", 1, request_id=request_id),
    )
    assert claim.status_code == 200
    assert claim.json()["event"]["status"] == "assigned"
    assert claim.json()["event"]["version"] == 2
    assert claim.json()["duplicate"] is False

    duplicate = client.post(
        "/api/admin/risk-events/risk-demo-001/actions",
        headers=admin_headers,
        json=action_payload("claim", 1, request_id=request_id),
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["action"]["id"] == claim.json()["action"]["id"]

    begin = client.post(
        "/api/admin/risk-events/risk-demo-001/actions",
        headers=admin_headers,
        json=action_payload("begin_review", 2),
    )
    assert begin.status_code == 200
    assert begin.json()["event"]["status"] == "reviewing"

    resolve = client.post(
        "/api/admin/risk-events/risk-demo-001/actions",
        headers=admin_headers,
        json=action_payload("resolve", 3, "已联系家属并建议安排专业评估。"),
    )
    assert resolve.status_code == 200
    assert resolve.json()["event"]["status"] == "resolved"

    close = client.post(
        "/api/admin/risk-events/risk-demo-001/actions",
        headers=admin_headers,
        json=action_payload("close", 4),
    )
    assert close.status_code == 200
    assert close.json()["event"]["status"] == "closed"

    audit = client.get(
        "/api/admin/audit-logs?targetType=risk_event&targetId=risk-demo-001",
        headers=admin_headers,
    ).json()
    actions = {item["action"] for item in audit["items"]}
    assert {"risk.claim", "risk.begin_review", "risk.resolve", "risk.close"}.issubset(actions)


def test_invalid_transition_and_stale_version_return_conflict(
    client: TestClient, admin_headers: dict[str, str]
):
    invalid = client.post(
        "/api/admin/risk-events/risk-demo-001/actions",
        headers=admin_headers,
        json=action_payload("close", 1),
    )
    assert invalid.status_code == 409

    claimed = client.post(
        "/api/admin/risk-events/risk-demo-001/actions",
        headers=admin_headers,
        json=action_payload("claim", 1),
    )
    assert claimed.status_code == 200

    stale = client.post(
        "/api/admin/risk-events/risk-demo-001/actions",
        headers=admin_headers,
        json=action_payload("begin_review", 1),
    )
    assert stale.status_code == 409


def test_audit_log_filters_and_actor_display_name(client: TestClient, admin_headers: dict[str, str]):
    client.get("/api/admin/risk-events/risk-demo-001", headers=admin_headers)

    matching = client.get(
        "/api/admin/audit-logs?action=risk.viewed&actorId=staff-admin-001&targetType=risk_event",
        headers=admin_headers,
    )
    assert matching.status_code == 200
    body = matching.json()
    assert body["total"] == 1
    assert body["items"][0]["actorDisplayName"] == "周老师"
    assert body["items"][0]["targetId"] == "risk-demo-001"

    empty = client.get(
        "/api/admin/audit-logs?action=risk.resolve&actorId=staff-admin-001",
        headers=admin_headers,
    )
    assert empty.status_code == 200
    assert empty.json()["items"] == []
