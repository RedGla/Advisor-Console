import models
from tests.helpers import auth_client, cleanup_user, create_user
from telemetry_service import record

def test_admin_events_are_bounded_sorted_and_metadata_only(client, db):
    admin = create_user(db, role="admin")
    user = create_user(db)
    for index in range(3):
        record(db, "provider_error" if index == 0 else "request_blocked", user_id=user.id,
               status="error", reason=f"reason-{index}", user_input="secret prompt", assistant_response="secret grounding")
    db.commit()
    try:
        response = auth_client(client, admin).get("/admin/events?limit=2")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["id"] != body[1]["id"]
        assert body[0]["created_at"] >= body[1]["created_at"]
        assert all("user_input" not in item and "assistant_response" not in item for item in body)
        assert all("grounding" not in str(item).lower() for item in body)
    finally:
        cleanup_user(str(admin.id)); cleanup_user(str(user.id))

def test_non_admin_cannot_read_events(client, db):
    user = create_user(db)
    try:
        response = auth_client(client, user).get("/admin/events")
        assert response.status_code == 403
    finally:
        cleanup_user(str(user.id))
