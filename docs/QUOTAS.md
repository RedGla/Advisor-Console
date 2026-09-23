# Phase 1: daily message quota correctness

## Admission and accounting

1. Validate ownership, then check the per-process rate limit. A rate rejection
   performs no daily-counter write, even if today's counter does not exist.
2. Insert today's counter with PostgreSQL `ON CONFLICT DO NOTHING` against
   `uq_usage_counters_user_day`, then `SELECT FOR UPDATE` the unique row.
   Refresh ORM state after obtaining the lock. Check caps and reserve one slot.
3. Commit the reservation, user message, pending assistant, and initial title
   together. A preparation/commit failure rolls back that entire transaction.
   No database lock spans the provider call.
4. On success, lock the pending assistant, add actual token/cost usage to the
   **reserved UTC day**, and mark the assistant completed in one transaction.
5. A Docs failure is known to precede the provider call: transition the assistant
   to error and release its message slot in one transaction. User/error messages
   remain available. A second finalization cannot release/reconcile twice,
   because only a locked pending assistant can transition.

Provider exceptions/timeouts have uncertain billing outcomes and retain the
message slot. Completion DB failures roll back token/cost updates and leave the
pending row and reserved slot intact. Process termination/cancellation after
admission also retains the slot. This conservative behavior prevents failures
from granting extra daily requests; automated crash recovery is not implemented.
The reservation reference is request-local, not a durable retry queue.

Daily message count therefore means retained admitted calls (including pending
or uncertain provider outcomes), not only successful replies. Rate admission is
an attempt limit: a request later rejected by the daily cap still occupies its
rate-window slot. The rate limiter remains process-local.

This phase fixes **message quota** admission and reconciliation races. The
existing token threshold blocks admission once reconciled tokens reach the cap,
but in-flight token reservation and provider output bounds remain a separate
unresolved audit finding; this change does not claim a strict total token budget.

## Migration and deployment

Revision `8b2c3d4e5f6a` follows `7a1e2f3c4d5e`. It takes an exclusive lock on
`usage_counters`, combines duplicate user/day rows into the smallest ID, sums
their recorded message/token/spend totals (NULL counts as zero), removes the
duplicates, and creates `UNIQUE(user_id, date_str)` in the same transaction.
Existing recorded usage is preserved; this cannot reconstruct previously lost
usage. Rows for other users/days are unchanged.

Apply migrations **before** starting the new backend code; its conflict target
requires the constraint. Schedule a brief write pause and take a database backup
before upgrading a deployed database, because consolidation locks this table.

From `backend/`, with the intended deployment's database configuration:

```text
python -m alembic upgrade head
```

This task only applies migrations to disposable test PostgreSQL. No production
database has been migrated. Downgrade removes the constraint; it cannot restore
the original separate duplicate rows. Roll back application code before removing
the constraint if a deployment rollback is needed.

## Verification

Start disposable PostgreSQL using [TESTING.md](TESTING.md), then at repository root:

```text
python -m pytest -q
python -m pytest -q backend/tests/test_cap_race.py backend/tests/test_rate_limit_race.py backend/tests/test_quota_correctness.py -k "concurrent or finish_is_once"
```

PowerShell repeat command (stop on first failure):

```powershell
1..10 | ForEach-Object {
    python -m pytest -q backend/tests/test_cap_race.py backend/tests/test_rate_limit_race.py backend/tests/test_quota_correctness.py -k 'concurrent or finish_is_once'
    if ($LASTEXITCODE -ne 0) { throw "Quota race pass $_ failed" }
}
```

CI runs the full suite and repeats the race selection five additional times,
uploading separate JUnit files. The first-request races use a barrier so both
HTTP requests reach get-or-create before either INSERT proceeds. Cases cover
one remaining slot, two available slots, and an existing counter at cap-minus-one;
each scenario has five repetitions per invocation. Assertions inspect database
row counts, quota totals, token/cost sums, stored turns, and provider call counts.

Other tests cover zero writes for rate-blocked users with/without existing rows,
exact message/token admission boundaries, duplicate constraint enforcement,
rollback before/after provider work, document-failure release, conservative
provider-timeout handling, refreshed ORM state, concurrent once-only finalization,
UTC-midnight attribution, and migration consolidation/constraint downgrade.
