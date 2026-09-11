from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import NotificationRecord, OutboxEvent
from app.db.session import SessionLocal
from app.services.notifications import (
    NOTIFICATION_EVENT_TYPE,
    InAppNotificationAdapter,
    process_next_notification_event,
)


def test_emergency_notifies_authorized_family_and_staff_without_duplicate_delivery(
    client: TestClient,
    elder_headers: dict[str, str],
    family_headers: dict[str, str],
    no_access_family_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    request = {
        "requestId": "notification-emergency-001",
        "source": "elder_button",
        "note": "合成联调求助",
    }
    created = client.post("/api/emergency/events", headers=elder_headers, json=request)
    duplicate = client.post("/api/emergency/events", headers=elder_headers, json=request)
    assert created.status_code == 201
    assert duplicate.status_code == 201
    assert duplicate.json()["duplicate"] is True

    family_list = client.get("/api/notifications/me", headers=family_headers)
    admin_list = client.get("/api/notifications/me", headers=admin_headers)
    denied_list = client.get("/api/notifications/me", headers=no_access_family_headers)
    assert family_list.status_code == 200
    assert family_list.json()["total"] == 1
    assert family_list.json()["unreadCount"] == 1
    assert family_list.json()["items"][0]["category"] == "emergency"
    assert admin_list.json()["total"] == 1
    assert denied_list.json()["total"] == 0

    notification_id = family_list.json()["items"][0]["id"]
    forbidden = client.post(f"/api/notifications/{notification_id}/read", headers=no_access_family_headers)
    first_read = client.post(f"/api/notifications/{notification_id}/read", headers=family_headers)
    duplicate_read = client.post(f"/api/notifications/{notification_id}/read", headers=family_headers)
    assert forbidden.status_code == 404
    assert first_read.status_code == 200
    assert first_read.json()["duplicate"] is False
    assert duplicate_read.json()["duplicate"] is True
    assert client.get("/api/notifications/me?unreadOnly=true", headers=family_headers).json()["total"] == 0

    with SessionLocal() as db:
        delivery_events = list(
            db.scalars(select(OutboxEvent).where(OutboxEvent.event_type == NOTIFICATION_EVENT_TYPE))
        )
        assert len(delivery_events) == 3
        assert all(
            set(event.payload_json) == {"notificationId", "recipientId", "channels"}
            for event in delivery_events
        )
        assert "合成联调求助" not in str([event.payload_json for event in delivery_events])
        outcomes = []
        while True:
            outcome = process_next_notification_event(db, adapter=InAppNotificationAdapter())
            if outcome is None:
                break
            outcomes.append(outcome)
        assert len(outcomes) == 3
        assert all(outcome.status == "processed" for outcome in outcomes)

    delivery_audits = client.get(
        "/api/admin/audit-logs?action=notification.delivered",
        headers=admin_headers,
    )
    assert delivery_audits.status_code == 200
    assert delivery_audits.json()["total"] == 3


def test_risk_request_action_notifies_only_family_with_care_action_scope(
    client: TestClient,
    admin_headers: dict[str, str],
    family_headers: dict[str, str],
    no_access_family_headers: dict[str, str],
) -> None:
    expected_version = 1
    for action, note in (
        ("claim", None),
        ("begin_review", None),
        ("request_action", "请家属今天完成一次温和联系。"),
    ):
        response = client.post(
            "/api/admin/risk-events/risk-demo-001/actions",
            headers=admin_headers,
            json={
                "requestId": f"notify-risk-{action}-001",
                "action": action,
                "expectedVersion": expected_version,
                "note": note,
            },
        )
        assert response.status_code == 200
        expected_version += 1

    family_items = client.get("/api/notifications/me", headers=family_headers).json()["items"]
    denied_items = client.get("/api/notifications/me", headers=no_access_family_headers).json()["items"]
    assert len(family_items) == 1
    assert family_items[0]["category"] == "risk_follow_up"
    assert family_items[0]["targetId"] == "risk-demo-001"
    assert denied_items == []


def test_grant_revocation_remains_visible_to_affected_family(
    client: TestClient,
    admin_headers: dict[str, str],
    family_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/admin/family-grants/family-demo-001/elder-demo-001/actions",
        headers=admin_headers,
        json={
            "action": "revoke",
            "expectedVersion": 1,
            "note": "合成授权撤回测试",
        },
    )
    assert response.status_code == 200

    notifications = client.get("/api/notifications/me", headers=family_headers)
    assert notifications.status_code == 200
    assert notifications.json()["total"] == 1
    assert notifications.json()["items"][0]["category"] == "authorization"
    assert "已撤销" in notifications.json()["items"][0]["body"]

    with SessionLocal() as db:
        record = db.scalar(
            select(NotificationRecord).where(NotificationRecord.recipient_id == "family-demo-001")
        )
        assert record is not None
        assert record.target_id == "elder-demo-001"


def test_approved_family_receives_registration_notification(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    password = "SyntheticPass-2026"
    application = client.post(
        "/api/auth/registration-applications",
        json={
            "displayName": "联调家属",
            "loginIdentifier": "notify-family@example.com",
            "relationship": "女儿",
            "elderName": "陈奶奶",
            "password": password,
            "consentVersion": "demo-consent-v1",
        },
    )
    assert application.status_code == 201
    approved = client.post(
        f"/api/admin/registration-applications/{application.json()['id']}/review",
        headers=admin_headers,
        json={
            "decision": "approved",
            "elderId": "elder-demo-001",
            "scopes": ["daily_summary", "care_actions"],
            "note": "合成身份与关系核验通过",
        },
    )
    assert approved.status_code == 200
    login = client.post(
        "/api/auth/login",
        json={"loginIdentifier": "notify-family@example.com", "password": password},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    notifications = client.get("/api/notifications/me", headers=headers)
    assert notifications.status_code == 200
    assert notifications.json()["total"] == 1
    assert notifications.json()["items"][0]["category"] == "registration"
