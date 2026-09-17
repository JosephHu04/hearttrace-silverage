from datetime import timedelta

from fastapi.testclient import TestClient

from app.db.models import AuditLog, DailyCheckIn, FamilyElderGrant
from app.db.session import SessionLocal


PRIVATE_REPORT = {"mood": 2, "sleep": 3, "socialWillingness": 4}


def test_daily_check_in_is_private_by_default_and_role_bound(
    client: TestClient,
    elder_headers: dict[str, str],
    family_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    assert client.post("/api/elder/check-ins", json=PRIVATE_REPORT, headers=family_headers).status_code == 403
    assert client.get("/api/elder/check-ins", headers=admin_headers).status_code == 403
    assert client.get("/api/admin/check-ins", headers=family_headers).status_code == 403

    created = client.post("/api/elder/check-ins", json=PRIVATE_REPORT, headers=elder_headers)
    assert created.status_code == 200
    body = created.json()
    assert body["shareWithFamily"] is False
    assert body["shareWithCareTeam"] is False
    assert body["mood"] == 2
    assert len(client.get("/api/elder/check-ins", headers=elder_headers).json()["items"]) == 1
    assert client.get("/api/family/elders/elder-demo-001/check-ins", headers=family_headers).json()["items"] == []
    assert client.get("/api/admin/check-ins", headers=admin_headers).json() == {"items": [], "total": 0}


def test_same_day_update_is_single_record_and_revokes_sharing_immediately(
    client: TestClient,
    elder_headers: dict[str, str],
    family_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    first = client.post(
        "/api/elder/check-ins",
        json={**PRIVATE_REPORT, "shareWithFamily": True, "shareWithCareTeam": True},
        headers=elder_headers,
    ).json()
    family = client.get("/api/family/elders/elder-demo-001/check-ins", headers=family_headers).json()
    assert family["items"] == [{"checkinDate": first["checkinDate"], **PRIVATE_REPORT}]
    staff = client.get("/api/admin/check-ins?attentionOnly=true", headers=admin_headers).json()
    assert staff["total"] == 1
    assert staff["items"][0]["attentionNeeded"] is True
    assert staff["items"][0]["elderId"] == "elder-demo-001"

    updated = client.post("/api/elder/check-ins", json=PRIVATE_REPORT, headers=elder_headers)
    assert updated.status_code == 200
    assert updated.json()["id"] == first["id"]
    assert client.get("/api/family/elders/elder-demo-001/check-ins", headers=family_headers).json()["items"] == []
    assert client.get("/api/admin/check-ins", headers=admin_headers).json()["total"] == 0
    with SessionLocal() as db:
        assert db.query(DailyCheckIn).count() == 1
        writes = db.query(AuditLog).filter(AuditLog.target_type == "daily_check_in").all()
        assert {item.action for item in writes} == {"daily_check_in.created", "daily_check_in.updated"}
        assert all("mood" not in item.metadata_json for item in writes)


def test_family_requires_live_grant_and_personal_share(
    client: TestClient,
    elder_headers: dict[str, str],
    family_headers: dict[str, str],
    no_access_family_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    client.post(
        "/api/elder/check-ins",
        json={**PRIVATE_REPORT, "shareWithFamily": True},
        headers=elder_headers,
    )
    assert client.get("/api/family/elders/elder-demo-001/check-ins", headers=no_access_family_headers).status_code == 403
    assert client.get("/api/family/elders/elder-demo-002/check-ins", headers=family_headers).status_code == 403
    with SessionLocal() as db:
        grant = db.get(FamilyElderGrant, ("family-demo-001", "elder-demo-001"))
        grant.is_active = False
        db.commit()
    assert client.get("/api/family/elders/elder-demo-001/check-ins", headers=family_headers).status_code == 403
    assert client.get("/api/admin/check-ins", headers=admin_headers).json()["total"] == 0


def test_validation_attention_and_bounds(
    client: TestClient,
    elder_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    for bad in (0, 6):
        assert client.post("/api/elder/check-ins", json={**PRIVATE_REPORT, "mood": bad}, headers=elder_headers).status_code == 422
    assert client.get("/api/elder/check-ins?days=31", headers=elder_headers).status_code == 422
    assert client.get("/api/admin/check-ins?perPage=101", headers=admin_headers).status_code == 422
    saved = client.post(
        "/api/elder/check-ins",
        json={"mood": 3, "sleep": 4, "socialWillingness": 5, "shareWithCareTeam": True},
        headers=elder_headers,
    )
    assert saved.status_code == 200
    assert client.get("/api/admin/check-ins?attentionOnly=true", headers=admin_headers).json()["total"] == 0
    assert client.get("/api/admin/check-ins", headers=admin_headers).json()["items"][0]["attentionNeeded"] is False


def test_older_check_in_sharing_can_be_revoked_without_changing_answers(
    client: TestClient,
    elder_headers: dict[str, str],
    family_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    created = client.post(
        "/api/elder/check-ins",
        json={**PRIVATE_REPORT, "shareWithFamily": True, "shareWithCareTeam": True},
        headers=elder_headers,
    ).json()
    with SessionLocal() as db:
        row = db.get(DailyCheckIn, created["id"])
        row.checkin_date -= timedelta(days=1)
        db.commit()
    other_elder = client.post("/api/auth/demo-login", json={"actorId": "elder-demo-002"}).json()
    other_headers = {"Authorization": f"Bearer {other_elder['accessToken']}"}
    path = f"/api/elder/check-ins/{created['id']}/sharing"
    assert client.post(path, json={"shareWithFamily": False, "shareWithCareTeam": False}, headers=other_headers).status_code == 404
    result = client.post(path, json={"shareWithFamily": False, "shareWithCareTeam": False}, headers=elder_headers)
    assert result.status_code == 200
    assert result.json()["mood"] == PRIVATE_REPORT["mood"]
    assert client.get("/api/family/elders/elder-demo-001/check-ins", headers=family_headers).json()["items"] == []
    assert client.get("/api/admin/check-ins", headers=admin_headers).json()["total"] == 0
    with SessionLocal() as db:
        entries = db.query(AuditLog).filter(AuditLog.action == "daily_check_in.sharing_updated").all()
        assert len(entries) == 1
        assert "mood" not in entries[0].metadata_json
