import pytest
from fastapi.testclient import TestClient

from app import main
from app.routers import auth


def test_demo_login_can_be_hidden_outside_demo_environment(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(auth.settings, "enable_demo_login", False)

    response = client.post("/api/auth/demo-login", json={"actorId": "family-demo-001"})

    assert response.status_code == 404
    assert response.json()["detail"] == "演示登录未启用"


def test_admin_password_login_works_when_demo_login_is_disabled(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(auth.settings, "enable_demo_login", False)
    login = client.post(
        "/api/auth/login",
        json={"loginIdentifier": "admin.demo@hearttrace.local", "password": "AdminDemo2026!"},
    )
    assert login.status_code == 200
    assert login.json()["actor"]["role"] == "admin"
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    assert client.get("/api/admin/registration-applications", headers=headers).status_code == 200
    assert client.post("/api/auth/demo-login", json={"actorId": "staff-admin-001"}).status_code == 404


def test_family_password_login_cannot_open_admin_registration_queue(client: TestClient):
    login = client.post(
        "/api/auth/login",
        json={"loginIdentifier": "lin.demo@hearttrace.local", "password": "FamilyDemo2026!"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    assert client.get("/api/admin/registration-applications", headers=headers).status_code == 403


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
