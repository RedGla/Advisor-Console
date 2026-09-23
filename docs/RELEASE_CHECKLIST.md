# Release and Demo Checklist

## Before release

- [ ] Run `pytest -q` from `backend/`.
- [ ] Run `npm run lint` and `npm run build` from `frontend/`.
- [ ] Apply all Alembic migrations to the target database.
- [ ] Confirm production `COOKIE_SECURE=true`, appropriate `COOKIE_SAMESITE`, and session expiry settings.
- [ ] Confirm OpenRouter and Google credentials exist only as server environment variables.
- [ ] Confirm admin caps/rate limits in `/admin/config`.
- [ ] Run `python eval/run_eval.py --dry-run` and inspect `eval/results.md` metadata and rubric.
- [ ] Run the live evaluator with a dedicated test account when provider access is available.

## Demo flow

- [ ] Register with a normalized email and verify short passwords are rejected.
- [ ] Log in, send a multi-turn conversation, log out, log back in, and reopen it.
- [ ] Show that the browser never receives system-prompt or grounding text.
- [ ] Show admin today versus all-time usage labels.
- [ ] Open an admin conversation and inspect status, timestamps, tokens, cost, and errors.
- [ ] Demonstrate a rate-limit block and a cap block with clear responses.
- [ ] Demonstrate Docs cache hit/miss behavior and, if possible, a live edit within TTL.
- [ ] Demonstrate provider, Docs cold-cache, stale-cache, and database failure handling.

## Evidence to retain

- [ ] Backend test output.
- [ ] Frontend lint/build output.
- [ ] `eval/results.md` generated for the release commit.
- [ ] Database migration revision.
- [ ] Screenshots or screen recording for manual network-secrecy and conversation-reopen checks.
