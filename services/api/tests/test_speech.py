from fastapi.testclient import TestClient

from app.routers import speech as speech_router
from app.services.speech import SynthesizedAudio


def test_speech_endpoints_require_elder_role(client: TestClient, family_headers: dict[str, str]):
    assert client.get("/api/speech/health").status_code == 401
    assert client.get("/api/speech/health", headers=family_headers).status_code == 403
    assert client.post("/api/speech/transcribe", headers=family_headers, content=b"wav").status_code == 403


def test_speech_health_reports_each_local_service(client: TestClient, elder_headers: dict[str, str], monkeypatch):
    async def ready():
        return {"asr": True, "tts": False}

    monkeypatch.setattr(speech_router, "speech_health", ready)
    response = client.get("/api/speech/health", headers=elder_headers)
    assert response.status_code == 200
    assert response.json() == {"asr": True, "tts": False, "provider": "funasr+fish-speech"}


def test_transcribe_forwards_wav_without_persisting_it(client: TestClient, elder_headers: dict[str, str], monkeypatch):
    captured = {}

    async def transcribe(wav: bytes):
        captured["wav"] = wav
        return "今天天气怎么样"

    monkeypatch.setattr(speech_router, "transcribe_with_funasr", transcribe)
    response = client.post(
        "/api/speech/transcribe",
        headers={**elder_headers, "Content-Type": "audio/wav"},
        content=b"RIFF-test-audio",
    )
    assert response.status_code == 200
    assert response.json() == {"text": "今天天气怎么样"}
    assert captured["wav"] == b"RIFF-test-audio"


def test_transcribe_rejects_non_wav(client: TestClient, elder_headers: dict[str, str]):
    response = client.post(
        "/api/speech/transcribe",
        headers={**elder_headers, "Content-Type": "audio/webm"},
        content=b"audio",
    )
    assert response.status_code == 415


def test_synthesis_returns_pcm_metadata(client: TestClient, elder_headers: dict[str, str], monkeypatch):
    async def synthesize(text: str):
        assert text == "您好，今天感觉怎么样？"
        return SynthesizedAudio(data=b"\x00\x00\x01\x00", sample_rate=44100)

    monkeypatch.setattr(speech_router, "synthesize_with_fish_speech", synthesize)
    response = client.post(
        "/api/speech/synthesize",
        headers=elder_headers,
        json={"text": "您好，今天感觉怎么样？"},
    )
    assert response.status_code == 200
    assert response.content == b"\x00\x00\x01\x00"
    assert response.headers["x-audio-format"] == "pcm_s16le"
    assert response.headers["x-audio-sample-rate"] == "44100"
