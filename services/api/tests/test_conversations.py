from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError, APITimeoutError

from companion_evaluate import assess_reply, load_cases
from app.services.companion.client import CompanionClient
from app.services.companion.live_info import build_live_info_result
from app.services.companion.policy import plan_care_turn
from app.services.companion.prompt import build_elder_prompt
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
        emergency_number="120",
    )

    assert plan.processing == "local_safety"
    assert plan.direct_reply is not None
    assert "120" in plan.direct_reply


def test_local_safety_covers_medication_fraud_and_abuse() -> None:
    medication = plan_care_turn(
        "我刚才多吃了一片药",
        turn_count=0,
        recent_user_messages=[],
        recent_openings=[],
    )
    fraud = plan_care_turn(
        "有人让我转账到安全账户",
        turn_count=0,
        recent_user_messages=[],
        recent_openings=[],
    )
    abuse = plan_care_turn(
        "家里人把我锁起来，不让我出门",
        turn_count=0,
        recent_user_messages=[],
        recent_openings=[],
    )

    assert medication.scene == "medication_safety"
    assert medication.processing == "local_safety"
    assert "拨打999" in (medication.direct_reply or "")
    assert fraud.scene == "fraud_safety"
    assert "暂停转账" in (fraud.direct_reply or "")
    assert abuse.scene == "personal_safety"
    assert "您现在安全吗" in (abuse.direct_reply or "")


def test_invalid_emergency_number_falls_back_to_safe_default() -> None:
    plan = plan_care_turn(
        "我突然胸痛",
        turn_count=0,
        recent_user_messages=[],
        recent_openings=[],
        emergency_number="call-anything",
    )

    assert "拨打999" in (plan.direct_reply or "")


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
    assert request["extra_body"] == {
        "enable_thinking": False,
        "preserve_thinking": False,
    }
    assert request["max_tokens"] == 160
    assert request["temperature"] == 0.3
    assert request["messages"][-2]["role"] == "system"
    assert "本轮硬性要求" in request["messages"][-2]["content"]
    assert request["messages"][-1] == {"role": "user", "content": "我想孙子了"}


def test_prompt_has_spoken_response_and_repair_contract() -> None:
    plan = plan_care_turn(
        "不对，我说的是电视遥控器没反应，不是手机",
        turn_count=2,
        recent_user_messages=["手机打不开"],
        recent_openings=["您可以先看看手机。"],
    )

    prompt = build_elder_prompt(plan.context)

    assert plan.care_mode == "repair_support"
    assert "35 至 90 个汉字" in prompt
    assert "最多只能出现一个问号" in prompt
    assert "最多两个具体选项" in prompt
    assert "不要再次复述错误理解" in prompt
    assert "输出前静默自检" in prompt


def test_two_recent_questions_force_a_statement_turn() -> None:
    plan = plan_care_turn(
        "吃了碗面，想起以前老伴做的面了",
        turn_count=4,
        recent_user_messages=[],
        recent_openings=["中午吃的什么？", "您今天吃过饭了吗？"],
        recent_question_count=2,
    )
    prompt = build_elder_prompt(plan.context)
    request_client = CompanionClient(get_settings())
    request_client._client = object()  # type: ignore[assignment]
    request = request_client.request_args(
        [{"role": "user", "content": "吃了碗面，想起以前老伴做的面了"}],
        plan.context,
    )
    normalized = CompanionClient._enforce_question_pause(
        "老伴做的面，您一直记着。她以前常做什么口味？",
        plan.context,
    )

    assert "不得有问号或疑问句" in prompt
    assert "不得包含问号、疑问词或任何疑问句" in request["messages"][-2]["content"]
    assert normalized == "老伴做的面，您一直记着。"
    assert "？" not in normalized


def test_stream_retries_one_immediate_connection_failure() -> None:
    class FlakyCompletions:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise APIConnectionError(
                    request=httpx.Request("POST", "https://example.invalid")
                )
            delta = SimpleNamespace(content="网络接上了。")
            return iter((SimpleNamespace(choices=[SimpleNamespace(delta=delta)]),))

    completions = FlakyCompletions()
    client = CompanionClient(get_settings())
    client._client = SimpleNamespace(  # type: ignore[assignment]
        chat=SimpleNamespace(completions=completions)
    )
    plan = plan_care_turn(
        "今天想说说话",
        turn_count=0,
        recent_user_messages=[],
        recent_openings=[],
    )

    _, chunks = client.stream_reply(
        [{"role": "user", "content": "今天想说说话"}], plan.context
    )

    assert list(chunks) == ["网络接上了。"]
    assert completions.calls == 2


def test_stream_does_not_retry_a_full_timeout() -> None:
    class TimeoutCompletions:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **_kwargs):
            self.calls += 1
            raise APITimeoutError(
                httpx.Request("POST", "https://example.invalid")
            )

    completions = TimeoutCompletions()
    client = CompanionClient(get_settings())
    client._client = SimpleNamespace(  # type: ignore[assignment]
        chat=SimpleNamespace(completions=completions)
    )
    plan = plan_care_turn(
        "今天想说说话",
        turn_count=0,
        recent_user_messages=[],
        recent_openings=[],
    )

    _, chunks = client.stream_reply(
        [{"role": "user", "content": "今天想说说话"}], plan.context
    )

    with pytest.raises(APITimeoutError):
        list(chunks)
    assert completions.calls == 1


def test_emotional_prompt_covers_grief_mixed_feelings_and_dependency_boundary() -> None:
    plan = plan_care_turn(
        "老伴去世后，我想给女儿打电话，又怕打扰她",
        turn_count=5,
        recent_user_messages=[],
        recent_openings=[],
    )

    prompt = build_elder_prompt(plan.context)

    assert plan.care_mode == "emotional_support"
    assert "不要把逝者说成仍然在世" in prompt
    assert "可以承认两部分" in prompt
    assert "用户表达了现实联系意愿" in prompt
    assert "低负担的联系动作" in prompt
    assert "我随时都在" in prompt


def test_policy_detects_social_and_reminiscence_phrasing() -> None:
    emotional = plan_care_turn(
        "女儿最近很忙，我已经两天没和人说话了",
        turn_count=0,
        recent_user_messages=[],
        recent_openings=[],
    )
    reminiscence = plan_care_turn(
        "我年轻时在纺织厂上夜班",
        turn_count=0,
        recent_user_messages=[],
        recent_openings=[],
    )

    assert emotional.care_mode == "emotional_support"
    assert reminiscence.care_mode == "reminiscence"


def test_practical_help_asks_for_current_screen_first() -> None:
    plan = plan_care_turn(
        "微信里的视频电话我不会开，怎么弄？",
        turn_count=0,
        recent_user_messages=[],
        recent_openings=[],
    )

    prompt = build_elder_prompt(plan.context)

    assert plan.care_mode == "practical_help"
    assert "用户没有说明当前屏幕" in prompt
    assert "不给任何操作步骤" in prompt


def test_history_budget_keeps_latest_complete_turns() -> None:
    history = [
        {"role": "user", "content": "早" * 60},
        {"role": "assistant", "content": "您好" * 20},
        {"role": "user", "content": "晚" * 20},
    ]

    selected = CompanionClient.bounded_history(history, character_budget=60)

    assert selected == history[-2:]


def test_companion_evaluation_corpus_and_quality_checks() -> None:
    cases = load_cases()
    repair_case = next(item for item in cases if item["id"] == "repair-adopts-correction")

    for case in cases:
        history = case["history"]
        recent_users = [
            item["content"]
            for item in reversed(history)
            if item["role"] == "user"
        ]
        recent_assistants = [
            item["content"]
            for item in reversed(history)
            if item["role"] == "assistant"
        ]
        plan = plan_care_turn(
            case["message"],
            turn_count=len(recent_users),
            recent_user_messages=recent_users,
            recent_openings=[item[:32] for item in recent_assistants],
            recent_question_count=sum(
                1
                for item in recent_assistants[:2]
                if "？" in item or "?" in item
            ),
        )
        assert plan.care_mode == case["expected"]["care_mode"], case["id"]

    passing = assess_reply(
        repair_case,
        "repair_support",
        "抱歉，听明白了，是电视遥控器没反应。可以先看看前端的小灯按键时会不会亮？",
    )
    failing = assess_reply(
        repair_case,
        "natural_adult",
        "老人家，手机屏幕是哪里不对？是不是坏了？",
    )

    assert len(cases) == 12
    assert all(passing.values())
    assert not all(failing.values())


def test_beijing_time_does_not_depend_on_system_tzdata() -> None:
    result = build_live_info_result("今天星期几？", get_settings())

    assert result is not None
    assert result.widget["kind"] == "time"
    assert "星期" in result.reply
