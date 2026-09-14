#!/usr/bin/env python3
"""Run a live elder -> admin -> family emergency and notification smoke test."""

from __future__ import annotations

import argparse
import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: dict[str, Any] | None = None,
        expected: int = 200,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=10) as response:
                status = response.status
                payload = json.loads(response.read() or b"{}")
        except HTTPError as error:
            status = error.code
            payload = json.loads(error.read() or b"{}")
        if status != expected:
            raise AssertionError(f"{method} {path}: expected {expected}, got {status}: {payload}")
        return payload

    def login(self, actor_id: str) -> str:
        result = self.request("POST", "/api/auth/demo-login", body={"actorId": actor_id})
        return str(result["accessToken"])


def matching_notification(items: list[dict[str, Any]], event_id: str, text: str | None = None) -> dict[str, Any]:
    matches = [
        item
        for item in items
        if item["targetType"] == "emergency_event"
        and item["targetId"] == event_id
        and (text is None or text in item["body"])
    ]
    if not matches:
        raise AssertionError(f"missing emergency notification for {event_id}, text={text!r}")
    return matches[0]


def run(base_url: str) -> dict[str, Any]:
    api = ApiClient(base_url)
    health = api.request("GET", "/api/health")
    assert health["status"] == "ok"

    elder_token = api.login("elder-demo-001")
    family_token = api.login("family-demo-001")
    no_access_token = api.login("family-no-access-001")
    admin_token = api.login("staff-admin-001")

    request_id = f"cross-client-{uuid4()}"
    created = api.request(
        "POST",
        "/api/emergency/events",
        token=elder_token,
        body={"requestId": request_id, "source": "elder_button", "note": "合成跨端联调求助"},
        expected=201,
    )
    event = created["event"]
    event_id = str(event["id"])
    assert event["status"] == "open" and created["duplicate"] is False

    duplicate = api.request(
        "POST",
        "/api/emergency/events",
        token=elder_token,
        body={"requestId": request_id, "source": "elder_button", "note": "合成跨端联调求助"},
        expected=201,
    )
    assert duplicate["duplicate"] is True and duplicate["event"]["id"] == event_id

    family_today = api.request("GET", "/api/family/elders/elder-demo-001/today", token=family_token)
    assert family_today["safety"]["hasActiveEmergency"] is True
    api.request("GET", "/api/family/elders/elder-demo-001/today", token=no_access_token, expected=403)

    family_inbox = api.request("GET", "/api/notifications/me", token=family_token)
    admin_inbox = api.request("GET", "/api/notifications/me", token=admin_token)
    denied_inbox = api.request("GET", "/api/notifications/me", token=no_access_token)
    family_created = matching_notification(family_inbox["items"], event_id)
    admin_created = matching_notification(admin_inbox["items"], event_id)
    assert not any(item["targetId"] == event_id for item in denied_inbox["items"])

    first_read = api.request("POST", f"/api/notifications/{family_created['id']}/read", token=family_token)
    repeated_read = api.request("POST", f"/api/notifications/{family_created['id']}/read", token=family_token)
    assert first_read["duplicate"] is False and repeated_read["duplicate"] is True
    api.request("POST", f"/api/notifications/{admin_created['id']}/read", token=admin_token)

    queue = api.request("GET", "/api/admin/emergency-events?status=open&elderId=elder-demo-001", token=admin_token)
    assert any(item["id"] == event_id for item in queue["items"])

    acknowledged = api.request(
        "POST",
        f"/api/admin/emergency-events/{event_id}/actions",
        token=admin_token,
        body={"requestId": f"{request_id}-ack", "action": "acknowledge", "expectedVersion": 1},
    )
    assert acknowledged["event"]["status"] == "acknowledged"
    family_inbox = api.request("GET", "/api/notifications/me", token=family_token)
    matching_notification(family_inbox["items"], event_id, "正在持续跟进")

    resolved = api.request(
        "POST",
        f"/api/admin/emergency-events/{event_id}/actions",
        token=admin_token,
        body={
            "requestId": f"{request_id}-resolve",
            "action": "resolve",
            "expectedVersion": 2,
            "note": "跨端联调：已使用合成账号确认安全。",
        },
    )
    assert resolved["event"]["status"] == "resolved"
    family_inbox = api.request("GET", "/api/notifications/me", token=family_token)
    matching_notification(family_inbox["items"], event_id, "已解除")
    family_after = api.request("GET", "/api/family/elders/elder-demo-001/today", token=family_token)
    assert family_after["safety"]["hasActiveEmergency"] is False

    audit = api.request(
        "GET",
        f"/api/admin/audit-logs?targetType=emergency_event&targetId={event_id}",
        token=admin_token,
    )
    actions = {item["action"] for item in audit["items"]}
    assert {"emergency.created", "emergency.acknowledge", "emergency.resolve"} <= actions

    return {
        "status": "passed",
        "eventId": event_id,
        "requestId": request_id,
        "verified": [
            "elder emergency creation and idempotency",
            "admin and authorized-family notification delivery",
            "unauthorized-family isolation",
            "family safety-state synchronization",
            "admin acknowledgement and resolution",
            "notification read idempotency and audit trail",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="Core API origin")
    args = parser.parse_args()
    print(json.dumps(run(args.api_base), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
