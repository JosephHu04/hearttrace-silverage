from datetime import timedelta

from app.db.models import OutboxEvent, utc_now
from app.db.session import SessionLocal
from app.services.analysis_pipeline import _claim_next_event
from app.services.notifications import _claim_notification_event


def test_final_attempt_crash_is_visible_and_can_be_requeued(client, admin_headers, family_headers):
    with SessionLocal() as db:
        for kind in ("conversation.analysis.requested", "notification.delivery.requested"):
            db.add(OutboxEvent(id=kind, event_type=kind, aggregate_type="test", aggregate_id="test",
                               dedupe_key=kind, payload_json={}, status="processing", attempts=3,
                               locked_at=utc_now() - timedelta(minutes=10)))
        db.commit()
        assert _claim_next_event(db) is None
        assert _claim_notification_event(db) is None
    assert client.get("/api/admin/operations/tasks", headers=family_headers).status_code == 403
    overview = client.get("/api/admin/operations/tasks", headers=admin_headers)
    assert overview.status_code == 200 and len(overview.json()["failed"]) == 2
    event_id = overview.json()["failed"][0]["id"]
    path = f"/api/admin/operations/tasks/{event_id}/retry"
    assert client.post(path, headers=family_headers).status_code == 403
    assert client.post(path, headers=admin_headers).status_code == 200
    assert client.post(path, headers=admin_headers).status_code == 409
    with SessionLocal() as db:
        event = db.get(OutboxEvent, event_id)
        assert event.status == "pending" and event.attempts == 0
