#!/usr/bin/env python3
"""Exercise the competition-critical workflow against a live HeartTrace API.

The script creates only synthetic, disposable data. Point it at a temporary
database-backed API, never at an environment containing real user data.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any
from uuid import uuid4

import httpx
import websockets


class Api:
    def __init__(self, base_url: str) -> None:
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=15)

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: dict[str, Any] | None = None,
        expected: int = 200,
    ) -> dict[str, Any]:
        response = self.client.request(
            method,
            path,
            headers={"Authorization": f"Bearer {token}"} if token else None,
            json=body,
        )
        if response.status_code != expected:
            raise AssertionError(
                f"{method} {path}: expected {expected}, got {response.status_code}: {response.text}"
            )
        return response.json() if response.content else {}

    def login(self, actor_id: str) -> str:
        return str(
            self.request("POST", "/api/auth/demo-login", body={"actorId": actor_id})[
                "accessToken"
            ]
        )


async def verify_realtime_conversation(ws_base: str, token: str, session_id: str) -> dict[str, Any]:
    async with websockets.connect(f"{ws_base.rstrip('/')}/api/realtime/conversation") as socket:
        await socket.send(
            json.dumps(
                {"type": "authenticate", "accessToken": token, "sessionId": session_id}
            )
        )
        ready = json.loads(await socket.recv())
        assert ready["type"] == "ready" and ready["sessionId"] == session_id
        await socket.send(json.dumps({"type": "message", "text": "这是合成测试：我现在想伤害自己。"}))
        events: list[dict[str, Any]] = []
        while True:
            event = json.loads(await socket.recv())
            events.append(event)
            if event.get("type") == "done":
                assert event.get("reply")
                assert event.get("model") == "local-safety-router"
                return {"ready": ready, "events": events}


def run(base_url: str, ws_base: str) -> dict[str, Any]:
    api = Api(base_url)
    assert api.request("GET", "/api/health")["status"] == "ok"
    assert api.request("GET", "/api/ready")["status"] == "ok"

    elder = api.login("elder-demo-001")
    family = api.login("family-demo-001")
    denied_family = api.login("family-no-access-001")
    admin = api.login("staff-admin-001")

    # Daily self-report: shared values are visible only to the selected audiences.
    check_in = api.request(
        "POST",
        "/api/elder/check-ins",
        token=elder,
        body={
            "mood": 2,
            "sleep": 3,
            "socialWillingness": 2,
            "shareWithFamily": True,
            "shareWithCareTeam": True,
        },
    )
    family_check_ins = api.request(
        "GET", "/api/family/elders/elder-demo-001/check-ins?days=7", token=family
    )
    assert any(item["checkinDate"] == check_in["checkinDate"] for item in family_check_ins["items"])
    api.request(
        "GET",
        "/api/family/elders/elder-demo-001/check-ins?days=7",
        token=denied_family,
        expected=403,
    )
    staff_check_ins = api.request(
        "GET", "/api/admin/check-ins?days=7&attentionOnly=true", token=admin
    )
    assert any(item["id"] == check_in["id"] and item["attentionNeeded"] for item in staff_check_ins["items"])

    # Standard screening: model-independent scoring, privacy-limited summaries and staff follow-up.
    screening = api.request(
        "POST",
        "/api/elder/screenings",
        token=elder,
        expected=201,
        body={
            "instrumentCode": "gad7",
            "consentConfirmed": True,
            "shareWithFamily": True,
            "shareWithCareTeam": True,
        },
    )
    for _ in range(7):
        question = screening["currentQuestion"]
        screening = api.request(
            "POST",
            f"/api/elder/screenings/{screening['id']}/answers",
            token=elder,
            body={"itemCode": question["itemCode"], "value": "3"},
        )
    assert screening["status"] == "completed"
    assert screening["result"]["totalScore"] == 21
    assert screening["result"]["band"] == "high"
    family_screenings = api.request(
        "GET", "/api/family/elders/elder-demo-001/screenings?days=30", token=family
    )
    shared_screening = next(item for item in family_screenings["items"] if item["id"] == screening["id"])
    assert shared_screening["band"] == "high"
    assert "totalScore" not in shared_screening and "answers" not in shared_screening
    api.request(
        "GET",
        "/api/family/elders/elder-demo-001/screenings?days=30",
        token=denied_family,
        expected=403,
    )
    staff_screenings = api.request("GET", "/api/admin/screenings?band=high", token=admin)
    assert any(item["id"] == screening["id"] for item in staff_screenings["items"])
    risks = api.request("GET", "/api/admin/risk-events?perPage=100", token=admin)
    assert any(item["id"] == f"risk-screening-{screening['id']}" for item in risks["items"])

    # Realtime conversation: use a deterministic local safety route so the smoke test needs no API key.
    session = api.request(
        "POST",
        "/api/conversations/sessions",
        token=elder,
        expected=201,
        body={"saveMessages": True, "allowAnalysis": True},
    )
    realtime = asyncio.run(verify_realtime_conversation(ws_base, elder, session["id"]))
    messages = api.request(
        "GET", f"/api/conversations/sessions/{session['id']}/messages", token=elder
    )
    assert [item["role"] for item in messages] == ["user", "assistant"]

    # Registration approval and password rotation.
    suffix = uuid4().hex[:10]
    identifier = f"competition-{suffix}@example.test"
    old_password = "SyntheticPass2026!"
    new_password = "SyntheticPass2026!Changed"
    application = api.request(
        "POST",
        "/api/auth/registration-applications",
        expected=201,
        body={
            "displayName": "比赛闭环测试家属",
            "loginIdentifier": identifier,
            "relationship": "子女",
            "elderName": "陈奶奶",
            "password": old_password,
            "consentVersion": "competition-smoke-v1",
        },
    )
    api.request(
        "POST",
        "/api/auth/login",
        body={"loginIdentifier": identifier, "password": old_password},
        expected=401,
    )
    api.request(
        "POST",
        f"/api/admin/registration-applications/{application['id']}/review",
        token=admin,
        body={
            "decision": "approved",
            "elderId": "elder-demo-001",
            "scopes": ["daily_summary", "care_actions"],
            "note": "合成身份与关系核验通过",
        },
    )
    family_login = api.request(
        "POST",
        "/api/auth/login",
        body={"loginIdentifier": identifier, "password": old_password},
    )
    new_family_token = str(family_login["accessToken"])
    linked_elders = api.request("GET", "/api/family/me/elders", token=new_family_token)
    assert [item["id"] for item in linked_elders["items"]] == ["elder-demo-001"]
    api.request(
        "GET", "/api/family/elders/elder-demo-002/today", token=new_family_token, expected=403
    )
    api.request(
        "POST",
        "/api/auth/password/change",
        token=new_family_token,
        body={"currentPassword": old_password, "newPassword": new_password},
    )
    api.request("GET", "/api/family/me/elders", token=new_family_token, expected=401)
    api.request(
        "POST",
        "/api/auth/login",
        body={"loginIdentifier": identifier, "password": old_password},
        expected=401,
    )
    api.request(
        "POST",
        "/api/auth/login",
        body={"loginIdentifier": identifier, "password": new_password},
    )

    return {
        "status": "passed",
        "syntheticFamily": identifier,
        "screeningId": screening["id"],
        "conversationSessionId": session["id"],
        "verified": [
            "health and readiness",
            "daily self-report sharing and access isolation",
            "deterministic GAD-7 scoring and privacy-limited summaries",
            "staff screening queue and risk-event creation",
            "realtime WebSocket safety response and message persistence",
            "registration approval, relationship isolation and password rotation",
        ],
        "realtimeEventTypes": [item["type"] for item in realtime["events"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--ws-base", default="ws://127.0.0.1:8000")
    args = parser.parse_args()
    print(json.dumps(run(args.api_base, args.ws_base), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
