from types import SimpleNamespace

import jwt

from app.db.models import FamilyElderGrant
from app.db.session import SessionLocal


def _configure(monkeypatch):
    from app.routers import voice_calls
    monkeypatch.setattr(voice_calls, "ensure_configured", lambda: None)


def test_authorized_family_elder_call_flow(client, family_headers, elder_headers, monkeypatch):
    _configure(monkeypatch)
    started = client.post("/api/voice-calls", headers=family_headers, json={"targetId": "elder-demo-001"})
    assert started.status_code == 200
    call = started.json()["call"]
    assert call["status"] == "ringing"
    assert client.get("/api/voice-calls/current", headers=elder_headers).json()["call"]["incoming"] is True
    assert client.post(f"/api/voice-calls/{call['id']}/token", headers=family_headers).status_code == 409
    assert client.post(f"/api/voice-calls/{call['id']}/answer", headers=family_headers).status_code == 409
    assert client.post("/api/voice-calls", headers=family_headers, json={"targetId": "elder-demo-001"}).status_code == 409
    answered = client.post(f"/api/voice-calls/{call['id']}/answer", headers=elder_headers)
    assert answered.status_code == 200
    assert answered.json()["call"]["status"] == "active"
    from app.routers import voice_calls
    monkeypatch.setattr(voice_calls, "get_settings", lambda: SimpleNamespace(
        livekit_url="ws://127.0.0.1:7880", livekit_api_key="devkey", livekit_api_secret="secret"))
    issued = client.post(f"/api/voice-calls/{call['id']}/token", headers=elder_headers)
    assert issued.status_code == 200
    claims = jwt.decode(issued.json()["token"], "secret", algorithms=["HS256"], audience=None)
    assert claims["video"]["room"] == f"hearttrace-{call['id']}"
    assert claims["video"]["canPublishSources"] == ["microphone"]
    assert client.post(f"/api/voice-calls/{call['id']}/end", headers=family_headers).status_code == 200
    assert client.get("/api/voice-calls/current", headers=elder_headers).json()["call"] is None


def test_unbound_family_cannot_call_or_read(client, family_headers, no_access_family_headers, elder_headers, monkeypatch):
    _configure(monkeypatch)
    assert client.post("/api/voice-calls", headers=no_access_family_headers,
                       json={"targetId": "elder-demo-001"}).status_code == 403
    call_id = client.post("/api/voice-calls", headers=family_headers,
                          json={"targetId": "elder-demo-001"}).json()["call"]["id"]
    assert client.post(f"/api/voice-calls/{call_id}/answer", headers=no_access_family_headers).status_code == 404
    assert client.post(f"/api/voice-calls/{call_id}/end", headers=no_access_family_headers).status_code == 404
    assert client.get("/api/voice-calls/current", headers=no_access_family_headers).json()["call"] is None


def test_revoked_grant_ends_call(client, family_headers, elder_headers, monkeypatch):
    _configure(monkeypatch)
    call_id = client.post("/api/voice-calls", headers=family_headers,
                          json={"targetId": "elder-demo-001"}).json()["call"]["id"]
    with SessionLocal() as db:
        grant = db.get(FamilyElderGrant, ("family-demo-001", "elder-demo-001"))
        grant.is_active = False
        db.commit()
    assert client.get("/api/voice-calls/current", headers=elder_headers).json()["call"] is None
    assert client.post(f"/api/voice-calls/{call_id}/answer", headers=elder_headers).status_code == 403
