from fastapi.testclient import TestClient


def create_elder_emergency(client: TestClient, elder_headers: dict[str, str], request_id: str = "sos-request-001"):
    return client.post(
        "/api/emergency/events",
        headers=elder_headers,
        json={"requestId": request_id, "source": "elder_button", "note": "老人主动按下求助键"},
    )


def test_elder_creates_idempotent_emergency_and_family_sees_it(
    client: TestClient,
    elder_headers: dict[str, str],
    family_headers: dict[str, str],
):
    created = create_elder_emergency(client, elder_headers)
    assert created.status_code == 201
    event = created.json()["event"]
    assert event["elderId"] == "elder-demo-001"
    assert event["status"] == "open"
    assert event["source"] == "elder_button"
    assert created.json()["duplicate"] is False

    duplicate = create_elder_emergency(client, elder_headers)
    assert duplicate.status_code == 201
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["event"]["id"] == event["id"]

    today = client.get("/api/family/elders/elder-demo-001/today", headers=family_headers)
    assert today.status_code == 200
    safety = today.json()["safety"]
    assert safety["hasActiveEmergency"] is True
    assert safety["message"] == "老人已发出紧急求助，请尽快确认其安全"
    assert safety["status"] == "open"
    assert safety["source"] == "elder_button"
    assert isinstance(safety["triggeredAt"], str)


def test_elder_cannot_create_event_for_another_elder(client: TestClient, elder_headers: dict[str, str]):
    response = client.post(
        "/api/emergency/events",
        headers=elder_headers,
        json={"requestId": "sos-request-spoof", "elderId": "elder-demo-002", "source": "elder_button"},
    )
    assert response.status_code == 403


def test_bound_device_can_create_but_cannot_target_other_elder(
    client: TestClient,
    device_headers: dict[str, str],
):
    created = client.post(
        "/api/emergency/events",
        headers=device_headers,
        json={"requestId": "device-sos-001", "elderId": "elder-demo-001", "source": "device_button"},
    )
    assert created.status_code == 201
    assert created.json()["event"]["triggerActorId"] == "device-demo-001"

    forbidden = client.post(
        "/api/emergency/events",
        headers=device_headers,
        json={"requestId": "device-sos-002", "elderId": "elder-demo-002", "source": "device_button"},
    )
    assert forbidden.status_code == 403


def test_family_and_admin_cannot_use_emergency_trigger(
    client: TestClient,
    family_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    payload = {"requestId": "invalid-role-sos", "elderId": "elder-demo-001", "source": "elder_button"}
    assert client.post("/api/emergency/events", headers=family_headers, json=payload).status_code == 403
    assert client.post("/api/emergency/events", headers=admin_headers, json=payload).status_code == 403


def test_admin_acknowledges_resolves_and_audits_emergency(
    client: TestClient,
    elder_headers: dict[str, str],
    family_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    event = create_elder_emergency(client, elder_headers, "sos-admin-flow").json()["event"]

    queue = client.get("/api/admin/emergency-events?status=open&elderId=elder-demo-001", headers=admin_headers)
    assert queue.status_code == 200
    assert queue.json()["total"] == 1
    assert queue.json()["items"][0]["id"] == event["id"]

    acknowledged = client.post(
        f"/api/admin/emergency-events/{event['id']}/actions",
        headers=admin_headers,
        json={"requestId": "sos-acknowledge-001", "action": "acknowledge", "expectedVersion": 1},
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["event"]["status"] == "acknowledged"
    assert acknowledged.json()["event"]["version"] == 2

    family_today = client.get("/api/family/elders/elder-demo-001/today", headers=family_headers)
    assert family_today.json()["safety"]["message"] == "紧急求助已被工作人员确认，正在持续跟进"

    missing_note = client.post(
        f"/api/admin/emergency-events/{event['id']}/actions",
        headers=admin_headers,
        json={"requestId": "sos-resolve-no-note", "action": "resolve", "expectedVersion": 2},
    )
    assert missing_note.status_code == 409

    resolved = client.post(
        f"/api/admin/emergency-events/{event['id']}/actions",
        headers=admin_headers,
        json={
            "requestId": "sos-resolve-001",
            "action": "resolve",
            "expectedVersion": 2,
            "note": "已电话确认老人安全，求助解除。",
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["event"]["status"] == "resolved"

    family_after = client.get("/api/family/elders/elder-demo-001/today", headers=family_headers)
    assert family_after.json()["safety"]["hasActiveEmergency"] is False

    audit = client.get(
        f"/api/admin/audit-logs?targetType=emergency_event&targetId={event['id']}",
        headers=admin_headers,
    )
    assert audit.status_code == 200
    assert {item["action"] for item in audit.json()["items"]} == {
        "emergency.created",
        "emergency.acknowledge",
        "emergency.resolve",
    }


def test_admin_action_rejects_stale_version_and_idempotency_mismatch(
    client: TestClient,
    elder_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    first = create_elder_emergency(client, elder_headers, "sos-conflict-001").json()["event"]
    second = create_elder_emergency(client, elder_headers, "sos-conflict-002").json()["event"]

    action = {
        "requestId": "sos-action-shared",
        "action": "acknowledge",
        "expectedVersion": 1,
    }
    assert client.post(
        f"/api/admin/emergency-events/{first['id']}/actions", headers=admin_headers, json=action
    ).status_code == 200

    stale = client.post(
        f"/api/admin/emergency-events/{first['id']}/actions",
        headers=admin_headers,
        json={"requestId": "sos-stale-001", "action": "resolve", "expectedVersion": 1, "note": "过期操作"},
    )
    assert stale.status_code == 409

    mismatch = client.post(
        f"/api/admin/emergency-events/{second['id']}/actions", headers=admin_headers, json=action
    )
    assert mismatch.status_code == 409
