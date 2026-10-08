import asyncio
import base64
import json
from io import BytesIO
from types import SimpleNamespace
import wave

import httpx
import pytest
from fastapi.testclient import TestClient

from app.routers import speech as speech_router
from app.routers import realtime_speech as realtime_speech_router
from app.services import speech as speech_service
from app.services.speech import SpeechServiceError, SynthesizedAudio
from app.core.config import get_settings


def _sample_wav() -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(b"\x00\x00\x01\x00")
    return buffer.getvalue()


def test_speech_endpoints_require_elder_role(client: TestClient, family_headers: dict[str, str]):
    assert client.get("/api/speech/health").status_code == 401
    assert client.get("/api/speech/health", headers=family_headers).status_code == 403
    assert client.post("/api/speech/transcribe", headers=family_headers, content=b"wav").status_code == 403


def test_speech_health_reports_provider_readiness(client: TestClient, elder_headers: dict[str, str], monkeypatch):
    async def ready():
        return {"asr": True, "tts": False}

    monkeypatch.setattr(speech_router, "speech_health", ready)
    response = client.get("/api/speech/health", headers=elder_headers)
    assert response.status_code == 200
    assert response.json() == {"asr": True, "tts": False, "provider": "dashscope", "realtimeAsr": True}


def test_realtime_asr_requires_elder_role(client: TestClient, family_headers: dict[str, str]):
    with client.websocket_connect("/api/realtime/speech") as websocket:
        websocket.send_json({"type": "authenticate", "accessToken": family_headers["Authorization"].removeprefix("Bearer ")})
        assert websocket.receive_json()["type"] == "error"


def test_realtime_asr_relays_pcm_and_returns_only_final_text(client: TestClient, elder_headers: dict[str, str], monkeypatch):
    sent = []

    class FakeCloud:
        def __init__(self):
            self.received = asyncio.Queue()
            self.received.put_nowait(json.dumps({"type": "session.created"}))
            self.received.put_nowait(json.dumps({"type": "session.updated"}))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def recv(self):
            return await self.received.get()

        async def send(self, value):
            event = json.loads(value)
            sent.append(event)
            if event["type"] == "session.finish":
                self.received.put_nowait(json.dumps({"type": "conversation.item.input_audio_transcription.completed", "transcript": "今天心情很好"}))
                self.received.put_nowait(json.dumps({"type": "session.finished"}))

    monkeypatch.setattr(realtime_speech_router, "connect", lambda *_, **__: FakeCloud())
    monkeypatch.setattr(realtime_speech_router, "get_settings", lambda: SimpleNamespace(
        speech_provider="dashscope", speech_dashscope_api_key="test-key",
        speech_dashscope_base_url="https://dashscope.aliyuncs.com",
        speech_asr_realtime_model="qwen3-asr-flash-realtime", speech_max_audio_bytes=8_000_000,
    ))
    with client.websocket_connect("/api/realtime/speech") as websocket:
        websocket.send_json({"type": "authenticate", "accessToken": elder_headers["Authorization"].removeprefix("Bearer ")})
        assert websocket.receive_json() == {"type": "ready"}
        websocket.send_bytes(b"\x00\x00" * 1600)
        websocket.send_json({"type": "finish"})
        assert websocket.receive_json() == {"type": "final", "text": "今天心情很好"}
    assert [event["type"] for event in sent] == [
        "session.update", "input_audio_buffer.append", "input_audio_buffer.commit", "session.finish"
    ]
    assert base64.b64decode(sent[1]["audio"]) == b"\x00\x00" * 1600


def test_transcribe_forwards_wav_without_persisting_it(client: TestClient, elder_headers: dict[str, str], monkeypatch):
    captured = {}

    async def transcribe(wav: bytes):
        captured["wav"] = wav
        return "今天天气怎么样"

    monkeypatch.setattr(speech_router, "transcribe_audio", transcribe)
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


def test_synthesis_returns_wav_metadata(client: TestClient, elder_headers: dict[str, str], monkeypatch):
    wav = _sample_wav()

    async def synthesize(text: str):
        assert text == "您好，今天感觉怎么样？"
        return SynthesizedAudio(data=wav, sample_rate=44100)

    monkeypatch.setattr(speech_router, "synthesize_audio", synthesize)
    response = client.post(
        "/api/speech/synthesize",
        headers=elder_headers,
        json={"text": "您好，今天感觉怎么样？"},
    )
    assert response.status_code == 200
    assert response.content == wav
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["x-audio-format"] == "wav"
    assert response.headers["x-audio-sample-rate"] == "44100"


def test_fish_speech_requests_decodable_wav(monkeypatch):
    captured = {}
    wav = _sample_wav()

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url, *, json, headers):
            captured.update(json)
            return httpx.Response(
                200, content=wav, headers={"X-Audio-Sample-Rate": "44100"},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(speech_service.httpx, "AsyncClient", lambda **_: FakeClient())
    result = asyncio.run(speech_service.synthesize_with_fish_speech("您好"))

    assert captured["format"] == "wav"
    assert captured["streaming"] is False
    assert result.data == wav
    assert result.audio_format == "wav"


def test_fish_speech_rejects_audio_with_wrong_container(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url, *, json, headers):
            return httpx.Response(200, content=b"not-a-wav", request=httpx.Request("POST", url))

    monkeypatch.setattr(speech_service.httpx, "AsyncClient", lambda **_: FakeClient())
    with pytest.raises(SpeechServiceError, match="invalid WAV"):
        asyncio.run(speech_service.synthesize_with_fish_speech("您好"))


def test_dashscope_asr_sends_wav_data_url_with_speech_only_key(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "speech_dashscope_api_key", "speech-test-key")
    original_client = httpx.AsyncClient
    wav = _sample_wav()

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer speech-test-key"
        assert request.url.path == "/compatible-mode/v1/chat/completions"
        import json
        payload = json.loads(request.content)
        assert payload["model"] == "qwen3-asr-flash"
        uri = payload["messages"][0]["content"][0]["input_audio"]["data"]
        assert uri.startswith("data:audio/wav;base64,")
        assert base64.b64decode(uri.split(",", 1)[1]) == wav
        return httpx.Response(200, json={"choices": [{"message": {"content": "今天天气很好"}}]})

    monkeypatch.setattr(speech_service.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    assert asyncio.run(speech_service.transcribe_with_dashscope(wav)) == "今天天气很好"


def test_dashscope_tts_downloads_only_approved_wav(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "speech_dashscope_api_key", "speech-test-key")
    original_client = httpx.AsyncClient
    wav = _sample_wav()
    audio_url = "http://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/synthetic.wav?signature=fake"

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            import json
            payload = json.loads(request.content)
            assert payload["model"] == "qwen-audio-3.0-tts-flash"
            assert payload["input"]["format"] == "wav"
            assert payload["input"]["voice"] == "longanlingxi"
            return httpx.Response(200, json={"output": {"audio": {"url": audio_url}}})
        assert str(request.url) == audio_url
        return httpx.Response(200, content=wav)

    monkeypatch.setattr(speech_service.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    result = asyncio.run(speech_service.synthesize_with_dashscope("您好"))
    assert result.data == wav
    assert result.sample_rate == 44100


def test_dashscope_tts_rejects_untrusted_audio_url(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "speech_dashscope_api_key", "speech-test-key")
    original_client = httpx.AsyncClient

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output": {"audio": {"url": "http://127.0.0.1/admin"}}})

    monkeypatch.setattr(speech_service.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    with pytest.raises(SpeechServiceError, match="untrusted"):
        asyncio.run(speech_service.synthesize_with_dashscope("您好"))
