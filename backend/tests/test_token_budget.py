import pytest

import models
import usage_service


def _user(db):
    user = models.User(email="token-test@example.com", hashed_password="x", role="user")
    db.add(user); db.commit(); db.refresh(user)
    return str(user.id)

def _reservation(db, user_id):
    counter = usage_service.get_or_create_today_counter(db, user_id)
    db.commit()
    return usage_service.QuotaReservation(str(counter.id), user_id, str(counter.date_str))


def test_zero_remaining_rejected(db):
    r = _reservation(db, _user(db))
    c = db.query(models.UsageCounter).filter_by(id=r.counter_id).one()
    c.tokens_today = 100
    db.commit()
    with pytest.raises(ValueError):
        usage_service.reserve_token_budget(db, r, prompt_tokens=1, max_completion_tokens=10, daily_cap=100)


def test_prompt_and_completion_are_reserved_atomically(db):
    r = _reservation(db, _user(db))
    budget = usage_service.reserve_token_budget(db, r, prompt_tokens=8, max_completion_tokens=50, daily_cap=10)
    assert budget.completion_tokens == 2
    c = db.query(models.UsageCounter).filter_by(id=r.counter_id).one()
    assert c.reserved_tokens_today == 10


def test_provider_failure_can_release_reservation(db):
    r = _reservation(db, _user(db))
    budget = usage_service.reserve_token_budget(db, r, prompt_tokens=2, max_completion_tokens=3, daily_cap=10)
    usage_service.release_token_budget(db, r, budget)
    db.commit()
    c = db.query(models.UsageCounter).filter_by(id=r.counter_id).one()
    assert c.tokens_today == 0
    assert c.reserved_tokens_today == 0
