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

class TokenCapExceededError(CapExceededError):
    pass


def reserve_daily_quota(db: Session, user_id: str, *, daily_message_cap: int | None = None,
                        daily_token_cap: int | None = None) -> usage_service.QuotaReservation:
    """Reserve one message under a row lock, without committing.

    The caller commits with the initial turn records or rolls everything back.
    Token usage is checked against reconciled consumption; this does not reserve
    an in-flight token budget or bound provider generation.
    """
    counter = usage_service.get_or_create_today_counter(db, user_id)

    messages_today = getattr(counter, "messages_today") or 0
    tokens_today = getattr(counter, "tokens_today") or 0

    if messages_today >= (daily_message_cap if daily_message_cap is not None else MAX_MESSAGES_PER_DAY) or tokens_today >= (daily_token_cap if daily_token_cap is not None else MAX_TOKENS_PER_DAY):
        raise CapExceededError()

    setattr(counter, "messages_today", messages_today + 1)
    # Caller commits this reservation together with the initial turn records.
    return usage_service.QuotaReservation(str(counter.id), user_id, str(counter.date_str))


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


def check_rate_limit(user_id: str, *, max_requests: int | None = None,
                     window_seconds: int | None = None) -> None:
    """Raise RateLimitedError if this user is over the request rate limit.
    On success, records this request so it counts toward the next check."""
    now = time.monotonic()
    max_requests = max_requests if max_requests is not None else RATE_LIMIT_MAX_REQUESTS
    window_seconds = window_seconds if window_seconds is not None else RATE_LIMIT_WINDOW_SECONDS
    window_start = now - window_seconds

    recent = [t for t in _request_log[user_id] if t > window_start]

    if len(recent) >= max_requests:
        oldest = min(recent)
        retry_after = window_seconds - (now - oldest)
        _request_log[user_id] = recent  # still prune, even though we're blocking
        raise RateLimitedError(retry_after_seconds=max(retry_after, 1))

    recent.append(now)
    _request_log[user_id] = recent
