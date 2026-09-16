import pytest
from fastapi.testclient import TestClient

from app import main
from app.routers import auth


def test_demo_login_can_be_hidden_outside_demo_environment(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(auth.settings, "enable_demo_login", False)

    response = client.post("/api/auth/demo-login", json={"actorId": "family-demo-001"})

    assert response.status_code == 404
    assert response.json()["detail"] == "演示登录未启用"


def test_production_rejects_demo_data_and_demo_login(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main.settings, "enable_demo_login", True)
    monkeypatch.setattr(main.settings, "seed_demo_data", False)
    monkeypatch.setattr(main.settings, "jwt_secret", "a-production-secret-that-is-long-enough")

    with pytest.raises(RuntimeError, match="必须关闭演示登录"):
        main.validate_runtime_settings()


def test_production_rejects_default_jwt_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main.settings, "enable_demo_login", False)
    monkeypatch.setattr(main.settings, "seed_demo_data", False)
    monkeypatch.setattr(main.settings, "jwt_secret", "development-only-change-me-32-bytes-minimum")

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        main.validate_runtime_settings()
