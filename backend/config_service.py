import limits
import models
import os
from sqlalchemy.orm import Session

_DEFAULTS = {
    "daily_message_cap": int(os.getenv("MAX_MESSAGES_PER_DAY", "50")),
    "daily_token_cap": int(os.getenv("MAX_TOKENS_PER_DAY", "50000")),
    "rate_limit_requests": int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "5")),
    "rate_limit_window_seconds": int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
}

def get(db: Session) -> dict[str, int]:
    # Preserve test/runtime overrides of the legacy module constants while
    # still using persisted values in normal operation.
    if any(getattr(limits, key_map) != value for key_map, value in {
        "MAX_MESSAGES_PER_DAY": _DEFAULTS["daily_message_cap"],
        "MAX_TOKENS_PER_DAY": _DEFAULTS["daily_token_cap"],
        "RATE_LIMIT_MAX_REQUESTS": _DEFAULTS["rate_limit_requests"],
        "RATE_LIMIT_WINDOW_SECONDS": _DEFAULTS["rate_limit_window_seconds"],
    }.items()):
        return {"daily_message_cap": limits.MAX_MESSAGES_PER_DAY, "daily_token_cap": limits.MAX_TOKENS_PER_DAY,
                "rate_limit_requests": limits.RATE_LIMIT_MAX_REQUESTS, "rate_limit_window_seconds": limits.RATE_LIMIT_WINDOW_SECONDS}
    row = db.query(models.AppConfig).filter_by(id=1).first()
    if row is None:
        return {"daily_message_cap": limits.MAX_MESSAGES_PER_DAY,
                "daily_token_cap": limits.MAX_TOKENS_PER_DAY,
                "rate_limit_requests": limits.RATE_LIMIT_MAX_REQUESTS,
                "rate_limit_window_seconds": limits.RATE_LIMIT_WINDOW_SECONDS}
    return {"daily_message_cap": row.daily_message_cap, "daily_token_cap": row.daily_token_cap,
            "rate_limit_requests": row.rate_limit_requests,
            "rate_limit_window_seconds": row.rate_limit_window_seconds}

def update(db: Session, values: dict[str, int]) -> models.AppConfig:
    row = db.query(models.AppConfig).filter_by(id=1).with_for_update().first()
    if row is None:
        row = models.AppConfig(id=1, **get(db))
        db.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    db.commit(); db.refresh(row)
    return row
