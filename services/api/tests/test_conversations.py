from fastapi.testclient import TestClient

from app.services.companion.client import CompanionClient
from app.services.companion.live_info import build_live_info_result
from app.services.companion.policy import plan_care_turn
from app.core.config import get_settings


def _create_session(
    client: TestClient,
    headers: dict[str, str],
    *,
    save_messages: bool = False,
    allow_analysis: bool = False,
) -> dict[str, object]:
    response = client.post(
        "/api/conversations/sessions",
        headers=headers,
        json={"saveMessages": save_messages, "allowAnalysis": allow_analysis},
    )
    assert response.status_code == 201
    return response.json()


def _token(headers: dict[str, str]) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


def _receive_until_done(websocket) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    while True:
        event = websocket.receive_json()
        events.append(event)
        if event.get("type") in {"done", "error"}:
            return events


def test_only_elder_can_create_conversation_session(
    client: TestClient,
    elder_headers: dict[str, str],
    family_headers: dict[str, str],
) -> None:
    unauthenticated = client.post("/api/conversations/sessions", json={})
    forbidden = client.post("/api/conversations/sessions", headers=family_headers, json={})
    created = client.post(
        "/api/conversations/sessions",
        headers=elder_headers,
        json={"saveMessages": False, "allowAnalysis": False},
    )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert created.status_code == 201
    assert created.json()["elderId"] == "elder-demo-001"


def test_time_reply_updates_widget_without_calling_model(
    client: TestClient,
    elder_headers: dict[str, str],
) -> None:
    session = _create_session(client, elder_headers)
    with client.websocket_connect("/api/realtime/conversation") as websocket:
        websocket.send_json(
            {
                "type": "authenticate",
                "accessToken": _token(elder_headers),
                "sessionId": session["id"],
            }
        )
        ready = websocket.receive_json()
        assert ready["type"] == "ready"

        websocket.send_json({"type": "message", "text": "现在几点了？"})
        events = _receive_until_done(websocket)

    assert any(item.get("type") == "widget" and item.get("kind") == "time" for item in events)
    done = events[-1]
    assert done["type"] == "done"
    assert done["model"] == "local-live-info"
    assert "北京时间" in done["reply"]


def test_messages_are_only_persisted_after_explicit_consent(
    client: TestClient,
    elder_headers: dict[str, str],
) -> None:
    unsaved = _create_session(client, elder_headers, save_messages=False)
    saved = _create_session(client, elder_headers, save_messages=True)

    for session in (unsaved, saved):
        with client.websocket_connect("/api/realtime/conversation") as websocket:
            websocket.send_json(
                {
                    "type": "authenticate",
                    "accessToken": _token(elder_headers),
                    "sessionId": session["id"],
                }
            )
            assert websocket.receive_json()["type"] == "ready"
            websocket.send_json({"type": "message", "text": "你在吗？"})
            assert _receive_until_done(websocket)[-1]["type"] == "done"

    unsaved_history = client.get(
        f"/api/conversations/sessions/{unsaved['id']}/messages", headers=elder_headers
    )
    saved_history = client.get(
        f"/api/conversations/sessions/{saved['id']}/messages", headers=elder_headers
    )
    assert unsaved_history.status_code == 200
    assert unsaved_history.json() == []
    assert [item["role"] for item in saved_history.json()] == ["user", "assistant"]


def test_safety_language_bypasses_generation() -> None:
    plan = plan_care_turn(
        "我摔倒了，现在起不来",
        turn_count=0,
        recent_user_messages=[],
        recent_openings=[],
    )

    assert plan.processing == "local_safety"
    assert plan.direct_reply is not None
    assert "120" in plan.direct_reply


def test_flash_request_is_short_non_thinking_generation() -> None:
    settings = get_settings()
    client = CompanionClient(settings)
    plan = plan_care_turn(
        "我想孙子了",
        turn_count=0,
        recent_user_messages=[],
        recent_openings=[],
    )
    client._client = object()  # type: ignore[assignment]

    request = client.request_args(
        [{"role": "user", "content": "我想孙子了"}],
        plan.context,
    )

    assert request["model"] == "qwen3.8-flash"
    assert request["extra_body"] == {"enable_thinking": False}
    assert request["max_tokens"] == 220


def test_beijing_time_does_not_depend_on_system_tzdata() -> None:
    result = build_live_info_result("今天星期几？", get_settings())

    assert result is not None
    assert result.widget["kind"] == "time"
    assert "星期" in result.reply
