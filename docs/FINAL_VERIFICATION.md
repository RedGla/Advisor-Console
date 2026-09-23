# Final PRD Verification

| Requirement | Implementation file | Test | Result | Manual verification if needed |
|---|---|---|---|---|
| FR-01 multi-turn chat | `backend/main.py`, `frontend/src/pages/Chat.tsx` | `backend/tests/test_provider_failure.py`, `test_long_history.py` | PASS | Send two turns and confirm prior context is reflected. |
| FR-02 server-only Google Docs prompt with TTL cache | `backend/docs_service.py`, `backend/llm_service.py` | `test_docs_failure.py`, `test_grounding_edge_cases.py` | PASS | Edit each Google Doc, wait up to configured TTL, send a new turn, and inspect the browser network panel. |
| FR-03 keyword grounding | `backend/llm_service.py` | `test_grounding_edge_cases.py`, eval grounding prompts | PASS | Verify a relevant query uses the reference content and an irrelevant query does not. |
| FR-04 stored conversations reopen | `backend/main.py`, `frontend/src/pages/Chat.tsx` | `test_ownership.py`, `test_long_history.py` | PASS | Log out, log back in, reopen each listed conversation, and confirm complete stored history renders. |
| FR-05 hard per-user message/token caps | `backend/limits.py`, `backend/usage_service.py` | `test_cap_race.py`, `test_quota_correctness.py`, `test_token_budget.py` | PASS | Over-cap requests return 429 and do not invoke the provider. |
| FR-06 rate limiting | `backend/limits.py`, `backend/main.py` | `test_rate_limit_race.py`, `test_quota_correctness.py` | PASS | Burst requests and confirm 429 plus retry guidance. |
| FR-07 durable turn/event logs | `backend/models.py`, `backend/telemetry_service.py` | `test_telemetry.py`, provider/docs/DB failure tests | PASS | Query `telemetry_events` after completed, blocked, and errored turns. |
| FR-08 admin usage and conversation review | `backend/main.py`, `frontend/src/pages/Admin.tsx` | `test_admin_console.py` | PASS | Open the admin page and inspect today/all-time labels and a conversation detail. |
| FR-09 evaluation evidence | `eval/run_eval.py`, `eval/results.md` | `eval/test_eval_artifact.py` | PASS | Run the live evaluator with configured test credentials. |
| NFR graceful failures | `backend/main.py`, `backend/docs_service.py` | `test_docs_failure.py`, `test_provider_failure.py`, `test_db_failure.py` | PASS | Confirm friendly 502/503 responses and telemetry entries. |
| NFR prompt/grounding secrecy | `backend/llm_service.py`, serializers in `backend/main.py` | extraction prompts p5/p6 and admin/user endpoint tests | PASS | Browser network inspection must show zero system-prompt or grounding text. |
| NFR maintainable prompt edits | `backend/docs_service.py` | cache hit/miss and outage tests | PASS | Live edit becomes visible after TTL without redeploy. |

## MVP metrics

- **Completed turns persisted:** assistant messages transition from `pending` to `completed` in `finish_reserved_turn`; the backend suite covers successful, provider-error, database-error, and retry paths. Target: ≥99% of completed turns persisted.
- **Google Doc changes visible within TTL:** `CACHE_TTL_SECONDS` governs cached system and grounding documents; cache-hit/miss tests and stale-cache fallback tests cover the behavior. Manual live edit verification is required for the deployment environment.
- **Cap violations hard-blocked:** row locks, unique daily counters, token reservations, and final reconciliation enforce the message/token invariant; concurrency and boundary tests pass.
- **Prompt/grounding client exposure:** serializers return message content and usage fields only; prompt extraction, grounding extraction, and network inspection are required release checks. Target: zero exposure.
- **Stored conversations fully reopen:** the conversation message endpoint returns all stored messages, while model context is bounded with summaries; UI reopening uses the complete stored list. Manual logout/login/reopen verification is required.
