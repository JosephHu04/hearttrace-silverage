from fastapi.testclient import TestClient


def application_payload() -> dict[str, str]:
    return {
        "displayName": "赵女士",
        "loginIdentifier": "zhao@example.com",
        "relationship": "子女",
        "elderName": "陈奶奶",
        "password": "safe-password-2026",
        "consentVersion": "family-registration-v1",
    }


def test_registration_requires_admin_approval_before_login(client: TestClient, admin_headers: dict[str, str]):
    submitted = client.post("/api/auth/registration-applications", json=application_payload())
    assert submitted.status_code == 201
    application = submitted.json()
    assert application["status"] == "pending"
    assert "password" not in application
    assert "passwordHash" not in application

    before_approval = client.post("/api/auth/login", json={"loginIdentifier": "zhao@example.com", "password": "safe-password-2026"})
    assert before_approval.status_code == 401

    queue = client.get("/api/admin/registration-applications", headers=admin_headers)
    assert queue.status_code == 200
    assert queue.json()["total"] == 1
    assert queue.json()["items"][0]["id"] == application["id"]

    approved = client.post(
        f"/api/admin/registration-applications/{application['id']}/review",
        headers=admin_headers,
        json={"decision": "approved", "elderId": "elder-demo-001", "note": "关系核验通过"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    login = client.post("/api/auth/login", json={"loginIdentifier": "zhao@example.com", "password": "safe-password-2026"})
    assert login.status_code == 200
    assert login.json()["actor"]["role"] == "family"
    elders = client.get("/api/family/me/elders", headers={"Authorization": f"Bearer {login.json()['accessToken']}"})
    assert elders.status_code == 200
    assert elders.json()["items"][0]["id"] == "elder-demo-001"


def test_approval_requires_admin_to_confirm_the_elder(client: TestClient, admin_headers: dict[str, str]):
    application = client.post("/api/auth/registration-applications", json=application_payload()).json()
    review = client.post(
        f"/api/admin/registration-applications/{application['id']}/review",
        headers=admin_headers,
        json={"decision": "approved"},
    )
    assert review.status_code == 400
    assert review.json()["detail"] == "通过申请前必须选择已核验的老人账号"


def test_approved_family_can_change_password_and_recovery_request_is_non_enumerating(client: TestClient, admin_headers: dict[str, str]):
    application = client.post("/api/auth/registration-applications", json=application_payload()).json()
    client.post(
        f"/api/admin/registration-applications/{application['id']}/review",
        headers=admin_headers,
        json={"decision": "approved", "elderId": "elder-demo-001"},
    )
    login = client.post("/api/auth/login", json={"loginIdentifier": "zhao@example.com", "password": "safe-password-2026"}).json()
    changed = client.post(
        "/api/auth/password/change",
        headers={"Authorization": f"Bearer {login['accessToken']}"},
        json={"currentPassword": "safe-password-2026", "newPassword": "even-safer-password-2026"},
    )
    assert changed.status_code == 200
    assert client.post("/api/auth/login", json={"loginIdentifier": "zhao@example.com", "password": "safe-password-2026"}).status_code == 401
    assert client.post("/api/auth/login", json={"loginIdentifier": "zhao@example.com", "password": "even-safer-password-2026"}).status_code == 200

    known = client.post("/api/auth/password-recovery", json={"loginIdentifier": "zhao@example.com"})
    unknown = client.post("/api/auth/password-recovery", json={"loginIdentifier": "unknown@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
