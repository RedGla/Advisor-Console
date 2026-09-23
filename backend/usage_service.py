"""Daily usage accounting. Transaction ownership stays with the turn handler."""

from dataclasses import dataclass
from datetime import timezone, datetime
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

import models


@dataclass(frozen=True)
class QuotaReservation:
    counter_id: str
    user_id: str
    date_str: str


@dataclass(frozen=True)
class TokenReservation:
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def get_or_create_today_counter(db: Session, user_id: str) -> models.UsageCounter:
    """Insert if absent, then lock the unique user/day row until caller commits.

    ON CONFLICT waits for a concurrent first insert without aborting this
    transaction. Refresh ORM state after acquiring the lock so a previously
    loaded counter cannot hide another transaction's committed reservation.
    """
    today = _today_str()
    db.execute(
        insert(models.UsageCounter)
        .values(user_id=user_id, date_str=today, messages_today=0,
                tokens_today=0, est_spend_today=0.0)
        .on_conflict_do_nothing(constraint="uq_usage_counters_user_day")
    )
    return (
        db.query(models.UsageCounter)
        .filter_by(user_id=user_id, date_str=today)
        .populate_existing()
        .with_for_update()
        .one()
    )


def reserve_token_budget(db: Session, reservation: QuotaReservation, *, prompt_tokens: int,
                         max_completion_tokens: int, daily_cap: int) -> TokenReservation:
    counter = _reserved_counter(db, reservation)
    used = (counter.tokens_today or 0) + (counter.reserved_tokens_today or 0)
    remaining = daily_cap - used
    if prompt_tokens > remaining:
        raise ValueError("insufficient token budget for prompt")
    completion = min(max_completion_tokens, remaining - prompt_tokens)
    if completion < 1:
        raise ValueError("insufficient token budget for completion")
    total = prompt_tokens + completion
    counter.reserved_tokens_today = (counter.reserved_tokens_today or 0) + total
    return TokenReservation(total, prompt_tokens, completion)


def release_token_budget(db: Session, reservation: QuotaReservation, token_reservation: TokenReservation) -> None:
    counter = _reserved_counter(db, reservation)
    counter.reserved_tokens_today = max(0, (counter.reserved_tokens_today or 0) - token_reservation.total_tokens)


def _reserved_counter(db: Session, reservation: QuotaReservation) -> models.UsageCounter:
    # Use the admitted day even if generation completes after UTC midnight.
    return (
        db.query(models.UsageCounter)
        .filter_by(id=reservation.counter_id, user_id=reservation.user_id,
                   date_str=reservation.date_str)
        .populate_existing()
        .with_for_update()
        .one()
    )


def reconcile_reservation(
    db: Session, reservation: QuotaReservation, *,
    prompt_tokens: int, completion_tokens: int, est_cost: float,
    token_reservation: TokenReservation | None = None,
    daily_cap: int | None = None,
) -> None:
    """Keep the reserved message slot and add actual usage; caller commits.

    The caller locks the associated pending assistant row and transitions it
    in the same transaction, preventing a second reconciliation of that turn.
    """
    counter = _reserved_counter(db, reservation)
    total = prompt_tokens + completion_tokens
    if token_reservation is not None:
        counter.reserved_tokens_today = max(0, (counter.reserved_tokens_today or 0) - token_reservation.total_tokens)
    if daily_cap is not None and (counter.tokens_today or 0) + total > daily_cap:
        raise ValueError("provider usage exceeded daily token cap")
    counter.tokens_today = (counter.tokens_today or 0) + total
    counter.est_spend_today = (counter.est_spend_today or 0.0) + est_cost


def release_reservation(db: Session, reservation: QuotaReservation) -> None:
    """Release a known pre-provider failure, with the turn's error transition."""
    counter = _reserved_counter(db, reservation)
    if not counter.messages_today or counter.messages_today < 1:
        raise RuntimeError("Cannot release an unreserved message slot")
    counter.messages_today -= 1
