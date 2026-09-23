import models
import telemetry_service


def test_telemetry_event_captures_turn_fields_without_prompt(db):
    user = models.User(email="telemetry@example.com", hashed_password="x", role="user")
    db.add(user); db.commit(); db.refresh(user)
    conversation = models.Conversation(user_id=user.id, title="t")
    db.add(conversation); db.commit(); db.refresh(conversation)
    telemetry_service.record(
        db, "llm_call_completed", user_id=user.id, conversation_id=conversation.id,
        status="completed", user_input="hello", assistant_response="hi",
        prompt_tokens=4, completion_tokens=2, estimated_cost=0.01,
    )
    db.commit()
    event = db.query(models.TelemetryEvent).filter_by(event="llm_call_completed").one()
    assert event.user_input == "hello"
    assert event.assistant_response == "hi"
    assert event.prompt_tokens == 4
    assert event.completion_tokens == 2
    assert not hasattr(event, "system_prompt")
    assert not hasattr(event, "grounding_document")


def test_required_event_names_are_supported(db):
    for name in ("message_sent", "request_blocked", "prompt_cache_hit",
                 "prompt_cache_miss", "doc_fetch_error", "provider_error"):
        telemetry_service.record(db, name, status="observed")
    db.commit()
    assert db.query(models.TelemetryEvent).count() == 6
