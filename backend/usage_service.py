"""
Write-through usage tracking (PRD §8): one usage_counters row per user per day,
updated on every completed LLM call. This is what the Day 8/9 daily caps and
the admin usage view will read from.
"""

from datetime import date, timezone, datetime
from sqlalchemy.orm import Session

import models


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def get_or_create_today_counter(db: Session, user_id: str) -> models.UsageCounter:
    today = _today_str()
    counter = (
        db.query(models.UsageCounter)
        .filter(
            models.UsageCounter.user_id == user_id,
            models.UsageCounter.date_str == today,
        )
        .first()
    )
    if counter is None:
        counter = models.UsageCounter(
            user_id=user_id,
            date_str=today,
            messages_today=0,
            tokens_today=0,
            est_spend_today=0.0,
        )
        db.add(counter)
        db.flush()  # get it into the session/id assigned without a full commit yet
    return counter


def record_usage(
    db: Session,
    user_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    est_cost: float,
) -> models.UsageCounter:
    """Increment today's counters for this user. Caller is responsible for
    committing (this function only adds to the session/flushes)."""
    counter = get_or_create_today_counter(db, user_id)

    current_messages = getattr(counter, "messages_today") or 0
    current_tokens = getattr(counter, "tokens_today") or 0
    current_spend = getattr(counter, "est_spend_today") or 0.0

    setattr(counter, "messages_today", current_messages + 1)
    setattr(counter, "tokens_today", current_tokens + prompt_tokens + completion_tokens)
    setattr(counter, "est_spend_today", current_spend + est_cost)

    return counter
