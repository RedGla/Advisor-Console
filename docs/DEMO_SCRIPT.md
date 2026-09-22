# Advisor Console — Demo Script

> **Audience**: Stakeholders, evaluators, sprint reviewers.
> **Duration**: ~10 minutes for a full walkthrough; 5 minutes for a quick highlights run.
> **Pre-requisites**: Backend running at `http://localhost:8000`, frontend at `http://localhost:5173`.

---

## Recommended Demo Flow

### 1. Context — What This Is (1 min)

> *"Advisor Console is a GPT-powered chat UI backed by FastAPI + Supabase Postgres.
> It has one distinctive feature: the advisor's persona and grounding context live
> in editable Google Docs — no redeploy needed to update what the model knows or
> how it responds."*

**Key talking points:**
- Advisors (admins) can edit the system prompt or grounding document live in Google Docs
- Changes propagate within the cache TTL (default 5 min) — no code change, no redeploy
- All conversations are persisted; the admin panel shows usage and spend per user

---

### 2. Login Flow (1 min)

Navigate to `http://localhost:5173`.

1. Enter credentials for a regular user account → **Login**
2. Point out: the session uses a **secure HTTP-only cookie** (no JWT in localStorage → no XSS token theft)
3. Show `/auth/me` returns role `"user"`

**Key talking point:**
> *"Session cookies with Argon2 password hashing. No MFA or OAuth in scope for this sprint — tracked as known limitation."*

---

### 3. Multi-Turn Chat (2 min)

1. Click **New Conversation**
2. Send a first message: *"What can you help me with today?"*
   - Point out the assistant replies in character (persona from the Google Doc)
3. Send a follow-up: *"Can you elaborate on point 2?"*
   - Point out the model receives the **full conversation history** — it correctly refers to "point 2" from the prior turn
4. Open DevTools → Network → show the POST to `/conversations/{id}/messages` response shape:
   ```json
   { "sender": "assistant", "status": "completed", "content": "...",
     "prompt_tokens": 312, "completion_tokens": 87, "est_cost": 0.000074 }
   ```

**Key talking points:**
- Token counts and cost are persisted on every message
- Assistant rows are written as `status=pending` *before* the LLM call — if the server crashes mid-call the turn still exists in the DB (≥99% persistence KPI)

---

### 4. Graceful Degradation Demo (2 min)

To demonstrate without actually killing Supabase or OpenRouter:

**LLM provider failure:**
> *"If OpenRouter is down or times out, the user sees a friendly message — never a stack trace."*

- Show `test_provider_failure.py` in the editor
- Or kill `OPENROUTER_API_KEY` in `.env` and send a message → see:
  > *"Sorry, I couldn't reach the advisor model right now. Please try again in a moment."*
- The assistant row is saved as `status=error` (not lost)

**DB connection failure:**
> *"If Supabase drops, every endpoint returns 503 with a plain-language message — not a 500 crash."*

- Reference `test_db_failure.py`

**Google Docs outage:**
> *"If the Docs API is unreachable but the cache is warm, conversations continue uninterrupted using the last-fetched prompt."*

---

### 5. Rate Limit & Daily Cap (1 min)

1. Show `limits.py` — two knobs: `RATE_LIMIT_MAX_REQUESTS` (burst) and `MAX_MESSAGES_PER_DAY`
2. Trigger a 429 via the test (`test_cap_race.py`) or by sending messages quickly
3. Response is:
   ```json
   { "reason": "rate", "message": "You are sending messages too quickly. Try again in 30s.", "retry_after_seconds": 30 }
   ```
   or for the daily cap:
   ```json
   { "reason": "cap", "message": "You have reached today's usage limit. Please try again tomorrow." }
   ```

**Key talking point:**
> *"Caps are enforced with a Postgres `SELECT FOR UPDATE` — even two concurrent requests at the limit can't both sneak through."*

---

### 6. Admin Panel (1 min)

1. Log out → log in as admin account
2. Navigate to `/admin` (or the Admin link in the sidebar)
3. Show the usage table: messages, tokens, estimated spend per user

**Key talking point:**
> *"Admins see aggregate spend in real-time. Useful for budget control without needing direct DB access."*

---

### 7. Live Prompt Editing (1 min — optional, requires Google Docs access)

1. Open the system-prompt Google Doc
2. Append a line: *"Always end your responses with 'Powered by Advisor Console.'"*
3. Wait ~5 minutes (or set `GOOGLE_DOCS_CACHE_TTL_SECONDS=10` for the demo)
4. Send a new chat message → the model now appends the new phrase

**Key talking point:**
> *"Zero-redeploy prompt iteration. The advisor persona can be tuned by non-engineers."*

---

### 8. Known Limitations (30 sec)

| Limitation | Detail |
|------------|--------|
| Keyword-only grounding | No vector search; synonym mismatches may miss relevant context |
| In-memory rate limiter | Resets on server restart (accepted trade-off; cap still enforced via DB) |
| Single persona | One system prompt for all users; no per-user persona switching |
| Cookie-only auth | No MFA, OAuth, or JWT refresh — scoped out of this sprint |

---

## Quick-Highlights Version (5 min)

Skip sections 4, 5, 7. Hit: Login → Multi-turn chat → Admin panel → known limitations.
