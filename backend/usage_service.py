"""
Write-through usage tracking (PRD §8): one usage_counters row per user per day,
updated on every completed LLM call. This is what the Day 8/9 daily caps and
the admin usage view will read from.
"""

from datetime import timezone, datetime
from sqlalchemy.orm import Session

import models


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def get_or_create_today_counter(db: Session, user_id: str) -> models.UsageCounter:
    """Fetch today's counter with a Postgres row lock (SELECT ... FOR UPDATE).

    Callers that check the daily cap must do so on this same Session before
    committing, so a concurrent request blocks here instead of both reading
    a stale count.
    """
    today = _today_str()
    counter = (
        db.query(models.UsageCounter)
        .filter(
            models.UsageCounter.user_id == user_id,
            models.UsageCounter.date_str == today,
        )
        .with_for_update()
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
        # Lock the row we just inserted so later waiters block on it.
        counter = (
            db.query(models.UsageCounter)
            .filter(models.UsageCounter.id == counter.id)
            .with_for_update()
            .one()
        )
    return counter


def record_usage(
    db: Session,
    user_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    est_cost: float,
) -> models.UsageCounter:
    """Add token/spend totals for a completed LLM call. The message slot was
    already reserved by limits.check_daily_cap under the same row lock.
    Caller is responsible for committing (this function only flushes)."""
    counter = get_or_create_today_counter(db, user_id)

    current_tokens = getattr(counter, "tokens_today") or 0
    current_spend = getattr(counter, "est_spend_today") or 0.0

    setattr(counter, "tokens_today", current_tokens + prompt_tokens + completion_tokens)
    setattr(counter, "est_spend_today", current_spend + est_cost)

    return counter
