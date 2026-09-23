from datetime import datetime, timezone
from database import SessionLocal
import models

def record(db, event: str, *, user_id=None, conversation_id=None, status=None,
           user_input=None, assistant_response=None, prompt_tokens=None,
           completion_tokens=None, estimated_cost=None, reason=None):
    row = models.TelemetryEvent(
        user_id=user_id, conversation_id=conversation_id, event=event,
        status=status, user_input=user_input, assistant_response=assistant_response,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        estimated_cost=estimated_cost, reason=reason,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    return row

def emit(event: str, **kwargs):
    db = SessionLocal()
    try:
        record(db, event, **kwargs)
        db.commit()
    finally:
        db.close()
