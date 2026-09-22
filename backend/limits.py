"""
Server-side caps and rate limiting (FR-05/FR-06). Enforced here, on the
backend, so a user can never bypass them from the client — the frontend
UI hiding the send button is a nicety, not the actual guardrail.

Two independent checks:
  - Daily cap: messages_today / tokens_today vs. env-configured limits,
    read from usage_counters (already being written to by usage_service.py).
  - Rate limit: a simple in-memory fixed window per user, no Redis.

NOTE on the rate limiter: it's a plain in-process dict, so it resets on
every backend restart (e.g. `--reload` picking up a code change, or a
redeploy). That's an accepted trade-off at this project's scope, not a
bug — don't "fix" it by reaching for Redis; that's explicitly off the
table per the plan's Do-Not-Build list.

NOTE on blocked-request telemetry: blocked requests (both daily cap and rate
limits) emit structured log events (`logger.warning("request_blocked reason=... user_id=...")`).
Emitting to server logs rather than an in-database events table is an intentional
design decision to avoid DB write-amplification under abusive bursts and keep the
schema minimal. In production, logs are collected by the platform log sink (e.g., Render/CloudWatch)
where queries and alerts can be executed externally.
"""

import os
import time
from collections import defaultdict
from sqlalchemy.orm import Session

import usage_service

# --- Daily caps -------------------------------------------------------

MAX_MESSAGES_PER_DAY = int(os.getenv("MAX_MESSAGES_PER_DAY", "50"))
MAX_TOKENS_PER_DAY = int(os.getenv("MAX_TOKENS_PER_DAY", "50000"))


class CapExceededError(Exception):
    """Raised when today's message or token usage is already at/over the cap."""
    pass


def check_daily_cap(db: Session, user_id: str) -> None:
    """Raise CapExceededError if this user is already at or over today's cap.

    Uses SELECT ... FOR UPDATE on today's usage_counters row (same Session /
    transaction as the caller) so a concurrent request blocks until this
    check finishes. Reserves one message slot while the row is locked so the
    increment cannot race with another check after the lock is released.
    """
    counter = usage_service.get_or_create_today_counter(db, user_id)

    messages_today = getattr(counter, "messages_today") or 0
    tokens_today = getattr(counter, "tokens_today") or 0

    if messages_today >= MAX_MESSAGES_PER_DAY or tokens_today >= MAX_TOKENS_PER_DAY:
        raise CapExceededError()

    setattr(counter, "messages_today", messages_today + 1)
    db.commit()


# --- Rate limiting ------------------------------------------------------

RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "5"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# user_id -> list of monotonic timestamps of recent requests.
# Module-level dict = in-memory only, per the note above.
_request_log: dict[str, list[float]] = defaultdict(list)


class RateLimitedError(Exception):
    """Raised when a user has made too many requests in the current window."""
    def __init__(self, retry_after_seconds: float):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limited, retry after {retry_after_seconds:.0f}s")


def check_rate_limit(user_id: str) -> None:
    """Raise RateLimitedError if this user is over the request rate limit.
    On success, records this request so it counts toward the next check."""
    now = time.monotonic()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS

    recent = [t for t in _request_log[user_id] if t > window_start]

    if len(recent) >= RATE_LIMIT_MAX_REQUESTS:
        oldest = min(recent)
        retry_after = RATE_LIMIT_WINDOW_SECONDS - (now - oldest)
        _request_log[user_id] = recent  # still prune, even though we're blocking
        raise RateLimitedError(retry_after_seconds=max(retry_after, 1))

    recent.append(now)
    _request_log[user_id] = recent
