from fastapi.testclient import TestClient


def registration_payload(identifier: str = "new-family@example.com") -> dict[str, str]:
    return {
        "displayName": "赵女士",
        "loginIdentifier": identifier,
        "relationship": "女儿",
        "elderName": "陈奶奶",
        "password": "safe-password-2026",
        "consentVersion": "family-registration-v1",
    }


def approve_family(client: TestClient, admin_headers: dict[str, str]) -> tuple[str, dict[str, str]]:
    application = client.post("/api/auth/registration-applications", json=registration_payload()).json()
    approved = client.post(
        f"/api/admin/registration-applications/{application['id']}/review",
        headers=admin_headers,
        json={
            "decision": "approved",
            "elderId": "elder-demo-001",
            "scopes": ["daily_summary", "care_actions"],
            "note": "已核验申请人与老人关系",
        },
    )
    assert approved.status_code == 200
    login = client.post(
        "/api/auth/login",
        json={"loginIdentifier": "new-family@example.com", "password": "safe-password-2026"},
    ).json()
    return login["actor"]["id"], {"Authorization": f"Bearer {login['accessToken']}"}


def test_approval_requires_verified_elder_and_creates_usable_grant(
    client: TestClient,
    admin_headers: dict[str, str],
):
    application = client.post("/api/auth/registration-applications", json=registration_payload()).json()
    missing_elder = client.post(
        f"/api/admin/registration-applications/{application['id']}/review",
        headers=admin_headers,
        json={"decision": "approved"},
    )
    assert missing_elder.status_code == 400

    approved = client.post(
        f"/api/admin/registration-applications/{application['id']}/review",
        headers=admin_headers,
        json={"decision": "approved", "elderId": "elder-demo-001"},
    )
    assert approved.status_code == 200
    login = client.post(
        "/api/auth/login",
        json={"loginIdentifier": "new-family@example.com", "password": "safe-password-2026"},
    ).json()
    headers = {"Authorization": f"Bearer {login['accessToken']}"}
    elders = client.get("/api/family/me/elders", headers=headers)
    assert elders.status_code == 200
    assert [item["id"] for item in elders.json()["items"]] == ["elder-demo-001"]
    assert client.get("/api/family/elders/elder-demo-001/today", headers=headers).status_code == 200
    assert client.get("/api/family/elders/elder-demo-002/today", headers=headers).status_code == 403


def test_admin_updates_scopes_revokes_and_reactivates_with_immediate_enforcement(
    client: TestClient,
    admin_headers: dict[str, str],
):
    family_id, family_headers = approve_family(client, admin_headers)
    grants = client.get("/api/admin/family-grants", headers=admin_headers)
    assert grants.status_code == 200
    grant = next(item for item in grants.json()["items"] if item["familyId"] == family_id)
    assert set(grant["scopes"]) == {"daily_summary", "care_actions"}

    updated = client.post(
        f"/api/admin/family-grants/{family_id}/elder-demo-001/actions",
        headers=admin_headers,
        json={"action": "update_scopes", "expectedVersion": grant["version"], "scopes": ["daily_summary"]},
    )
    assert updated.status_code == 200
    assert updated.json()["scopes"] == ["daily_summary"]
    assert client.get("/api/family/elders/elder-demo-001/today", headers=family_headers).status_code == 200
    care_action = client.post(
        "/api/family/risk-events/risk-demo-001/actions",
        headers=family_headers,
        json={"requestId": "new-family-care-action", "action": "contacted"},
    )
    assert care_action.status_code == 403

    stale = client.post(
        f"/api/admin/family-grants/{family_id}/elder-demo-001/actions",
        headers=admin_headers,
        json={"action": "revoke", "expectedVersion": grant["version"], "note": "使用过期版本"},
    )
    assert stale.status_code == 409

    revoked = client.post(
        f"/api/admin/family-grants/{family_id}/elder-demo-001/actions",
        headers=admin_headers,
        json={"action": "revoke", "expectedVersion": updated.json()["version"], "note": "老人要求撤回授权"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["isActive"] is False
    assert client.get("/api/family/me/elders", headers=family_headers).json()["items"] == []
    assert client.get("/api/family/elders/elder-demo-001/today", headers=family_headers).status_code == 403

    reactivated = client.post(
        f"/api/admin/family-grants/{family_id}/elder-demo-001/actions",
        headers=admin_headers,
        json={"action": "reactivate", "expectedVersion": revoked.json()["version"], "note": "老人重新确认授权"},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["isActive"] is True
    assert client.get("/api/family/elders/elder-demo-001/today", headers=family_headers).status_code == 200

    audit = client.get(
        "/api/admin/audit-logs?targetType=family_elder_grant",
        headers=admin_headers,
    )
    actions = {item["action"] for item in audit.json()["items"] if item["targetId"] == f"{family_id}:elder-demo-001"}
    assert actions == {"grant.created", "grant.update_scopes", "grant.revoke", "grant.reactivate"}


def test_only_admin_can_manage_relationships(client: TestClient):
    professional = client.post("/api/auth/demo-login", json={"actorId": "staff-professional-001"}).json()
    headers = {"Authorization": f"Bearer {professional['accessToken']}"}
    assert client.get("/api/admin/elders", headers=headers).status_code == 403
    assert client.get("/api/admin/family-grants", headers=headers).status_code == 403
