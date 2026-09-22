# Sept 17–18 Hardening Sprint — Pass/Fail Writeup

> **Scope**: Two-day hardening sprint covering graceful degradation of all three
> external dependencies (LLM provider, Google Docs, database), ownership/RBAC
> isolation, daily-cap race-condition fix, and evaluation tooling.

---

## What Was Hardened

| # | Area | Change | Files |
|---|------|--------|-------|
| 1 | **LLM provider failure** | Catch `httpx.TimeoutException`, `HTTPStatusError`, malformed body; return 502 + plain-language error message; persist assistant row as `status=error` | `main.py`, `llm_service.py` |
| 2 | **Google Docs failure (cold cache)** | `DocsServiceError` propagates to 502; test proves no raw exception leaks to client | `docs_service.py`, `main.py` |
| 3 | **Google Docs failure (warm cache)** | Stale-cache fallback — if Docs API is down but a cached copy exists, the LLM call proceeds normally | `docs_service.py` |
| 4 | **Daily-cap race condition** | Replaced unguarded counter check with `SELECT … FOR UPDATE` row locking via SQLAlchemy; concurrent requests at cap-minus-one correctly block the second | `limits.py`, `main.py` |
| 5 | **Ownership / RBAC isolation** | Added tests proving users cannot read, rename, delete, or send messages to conversations they do not own (IDOR prevention) | `tests/test_ownership.py` |
| 6 | **DB connection-drop handling** | Added `pool_pre_ping=True` + 5 s connect timeout; `get_db_or_503` dependency converts `OperationalError` → HTTP 503 with plain-language message | `database.py`, `main.py` |
| 7 | **Env var mismatch** | `docs_service._credentials()` now accepts either `GOOGLE_SERVICE_ACCOUNT_JSON_B64` (Render/production) or `GOOGLE_SERVICE_ACCOUNT_JSON` (local dev plain JSON); both example files updated | `docs_service.py`, `.env.example`, `env.example` |
| 8 | **Eval script bugs** | Fixed bearer-token auth assumption → cookie auth; fixed 404s from posting to non-existent conversations; corrected response-shape parsing; added `--dry-run` flag | `eval/run_eval.py` |

---

## Test Results

All tests were run via:

```bash
cd backend
python -m pytest tests/ -v
```

### Passing Tests

| Test file | Tests | Result |
|-----------|-------|--------|
| `test_provider_failure.py` | `test_llm_provider_timeout` | ✅ PASS |
| | `test_llm_provider_500` | ✅ PASS |
| | `test_llm_provider_malformed_body` | ✅ PASS |
| `test_docs_failure.py` | `test_docs_service_failure_no_cache` | ✅ PASS |
| | `test_docs_service_failure_warm_cache` | ✅ PASS |
| `test_ownership.py` | `test_cannot_read_other_users_conversations` | ✅ PASS |
| | `test_cannot_send_message_to_other_users_conversation` | ✅ PASS |
| | `test_cannot_rename_other_users_conversation` | ✅ PASS |
| | `test_cannot_delete_other_users_conversation` | ✅ PASS |
| | `test_admin_can_list_all_conversations` | ✅ PASS |
| `test_cap_race.py` | `test_only_one_of_two_concurrent_messages_succeeds_at_cap_minus_one` | ✅ PASS |
| `test_db_failure.py` | `test_db_connection_drop_on_list_conversations` | ✅ PASS |
| | `test_db_connection_drop_on_get_messages` | ✅ PASS |
| | `test_db_connection_drop_on_message_send` | ✅ PASS |

### Pre-existing Gap Fixed During Sprint

- **Cap race condition** (commit `0d15063`): Before the fix, two concurrent
  requests at `MAX_MESSAGES_PER_DAY - 1` could both pass the cap check and
  both succeed, over-spending the daily budget.  Fixed with Postgres row
  locking.

### Known Remaining Gaps

| Gap | Risk | Mitigation |
|-----|------|------------|
| In-memory rate limiter resets on restart | Low (reset is brief; cap still enforced) | Tracked as future Redis work |
| `test_db_failure.py` test 3 relies on patching `Session.commit` at the ORM level — if SQLAlchemy changes internals this may need updating | Very low | Noted in test docstring |
| Eval results table requires a live server; rubric rows 1–3 are self-assessed | Medium | Run `eval/run_eval.py` against a real server to populate |

---

## What Passed / What Was Fixed

### Already working before sprint
- LLM provider timeout and 5xx — covered by `test_provider_failure.py`
- Docs service cold-cache failure — covered by `test_docs_failure.py`
- Ownership isolation — covered by `test_ownership.py`

### Fixed during sprint
- Cap race condition (`test_cap_race.py` was written to *prove* the bug then
  prove the fix — the test now passes consistently with row locking)
- DB connection-drop degradation (new `test_db_failure.py`)
- Env var mismatch (`GOOGLE_SERVICE_ACCOUNT_JSON_B64` vs plain JSON)
- Eval script auth/conversation-creation bugs

---

## Commit Trail

```
80768b6  hardening and evaluation tests, frontend changes
0d15063  fix(backend): prevent daily cap race condition with Postgres row locking
94b63da  test(backend): add ownership and RBAC tests proving isolation and no IDOR
4aed076  feat: add message status/cost tracking, usage_counters write-through,
         and server-side caps + rate limiting (FR-05/FR-06)
```
