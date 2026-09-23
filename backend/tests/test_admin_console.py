from tests.helpers import create_user, auth_client, cleanup_user
import models

def test_admin_can_inspect_conversation_messages(client, db):
    admin = create_user(db, role="admin")
    user = create_user(db)
    conversation = models.Conversation(user_id=user.id, title="Audit")
    db.add(conversation); db.commit(); db.refresh(conversation)
    db.add_all([
        models.Message(conversation_id=conversation.id, sender="user", content="hello", status="completed"),
        models.Message(conversation_id=conversation.id, sender="assistant", content="hi", status="completed", prompt_tokens=3, completion_tokens=2, est_cost=0.01),
    ])
    db.commit()
    try:
        response = auth_client(client, admin).get(f"/admin/conversations/{conversation.id}/messages")
        assert response.status_code == 200
        body = response.json()
        assert [item["sender"] for item in body] == ["user", "assistant"]
        assert body[1]["prompt_tokens"] == 3
        assert body[1]["completion_tokens"] == 2
    finally:
        cleanup_user(str(admin.id)); cleanup_user(str(user.id))

def test_non_admin_cannot_inspect_conversation_messages(client, db):
    user = create_user(db)
    conversation = models.Conversation(user_id=user.id, title="Private")
    db.add(conversation); db.commit(); db.refresh(conversation)
    try:
        response = auth_client(client, user).get(f"/admin/conversations/{conversation.id}/messages")
        assert response.status_code == 403
    finally:
        cleanup_user(str(user.id))
