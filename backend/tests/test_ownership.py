"""Cross-user conversation access must 404; non-admins must not hit admin routes."""

import models
from tests.helpers import auth_client, cleanup_user, create_user


def test_user_cannot_access_another_users_conversation_or_messages(client, db):
    user_a = create_user(db)
    user_b = create_user(db)

    try:
        auth_client(client, user_a)
        created = client.post("/conversations", json={"title": "A's chat"})
        assert created.status_code == 200
        conversation_id = created.json()["id"]

        auth_client(client, user_b)
        get_messages = client.get(f"/conversations/{conversation_id}/messages")
        patch_conv = client.patch(
            f"/conversations/{conversation_id}",
            json={"title": "hijacked"},
        )
        delete_conv = client.delete(f"/conversations/{conversation_id}")

        post_msg = client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "hijack message"},
        )

        assert get_messages.status_code == 404
        assert patch_conv.status_code == 404
        assert delete_conv.status_code == 404
        assert post_msg.status_code == 404

        list_convs = client.get("/conversations")
        assert list_convs.status_code == 200
        assert all(c["id"] != conversation_id for c in list_convs.json())

        still_there = (
            db.query(models.Conversation)
            .filter(models.Conversation.id == conversation_id)
            .first()
        )
        assert still_there is not None
        assert still_there.title == "A's chat"
    finally:
        cleanup_user(str(user_a.id))
        cleanup_user(str(user_b.id))


def test_non_admin_cannot_access_admin_routes(client, db):
    user = create_user(db, role="user")
    try:
        auth_client(client, user)
        usage = client.get("/admin/usage")
        conversations = client.get("/admin/conversations")
        assert usage.status_code == 403
        assert conversations.status_code == 403
    finally:
        cleanup_user(str(user.id))
