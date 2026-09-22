"""get_or_create_today_counter must return a fresh zeroed row when only
yesterday's counter exists — it must never reuse a stale date_str row."""

import pytest
from datetime import datetime, timezone, timedelta

import models
import usage_service
from tests.helpers import create_user, cleanup_user


@pytest.fixture
def test_user(db):
    user = create_user(db)
    yield user
    cleanup_user(str(user.id))


def test_yesterday_counter_not_reused(db, test_user):
    """Insert a usage_counters row dated yesterday with non-zero counts,
    then call get_or_create_today_counter.  It must create a new row
    for today with zeroed counters, not return yesterday's."""
    user_id = str(test_user.id)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    today = datetime.now(timezone.utc).date().isoformat()

    # Plant yesterday's counter with real usage.
    old_counter = models.UsageCounter(
        user_id=user_id,
        date_str=yesterday,
        messages_today=42,
        tokens_today=12345,
        est_spend_today=0.99,
    )
    db.add(old_counter)
    db.commit()

    # Now ask for today's counter — should get a fresh one.
    counter = usage_service.get_or_create_today_counter(db, user_id)
    db.commit()

    assert counter.date_str == today, (
        f"Expected today's date {today} but got {counter.date_str}"
    )
    assert counter.messages_today == 0
    assert counter.tokens_today == 0
    assert counter.est_spend_today == 0.0

    # The old row must still exist untouched.
    old = (
        db.query(models.UsageCounter)
        .filter(
            models.UsageCounter.user_id == user_id,
            models.UsageCounter.date_str == yesterday,
        )
        .first()
    )
    assert old is not None
    assert old.messages_today == 42
    assert old.tokens_today == 12345


def test_today_counter_reused_when_exists(db, test_user):
    """If today's counter already exists, get_or_create_today_counter must
    return the same row, not create a duplicate."""
    user_id = str(test_user.id)
    today = datetime.now(timezone.utc).date().isoformat()

    # Create today's counter with some usage.
    existing = models.UsageCounter(
        user_id=user_id,
        date_str=today,
        messages_today=5,
        tokens_today=1000,
        est_spend_today=0.05,
    )
    db.add(existing)
    db.commit()
    db.refresh(existing)
    existing_id = existing.id

    counter = usage_service.get_or_create_today_counter(db, user_id)
    db.commit()

    assert counter.id == existing_id, "Should reuse the existing row"
    assert counter.messages_today == 5
    assert counter.tokens_today == 1000
