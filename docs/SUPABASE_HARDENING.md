# Supabase hardening runbook

## Migration

`ef56ab67bc90_lock_down_public_schema` enables RLS on every current public
application table, including `alembic_version`. It intentionally creates no
`anon` or `authenticated` policies because application traffic uses the
server-side PostgreSQL `postgres` role. The migration revokes direct public,
`anon`, `authenticated`, and `service_role` table and sequence privileges, then
sets matching default privileges for future application tables. It also adds
indexes for `conversations(user_id)` and `messages(conversation_id)`.

## Production preflight

1. Take a Supabase production backup and retain its restore identifier.
2. Record deployed backend commit and health response.
3. Schedule a short write pause for migration application and verification.
4. Confirm backend `DATABASE_URL` connects as `postgres`; it must not use
   `anon`, `authenticated`, or `service_role`.
5. Review the migration against a disposable PostgreSQL database or Supabase
   staging branch. Do not apply it to production before this succeeds.

## Advisor baseline — 2026-09-23

Security: RLS disabled on `alembic_version`, `users`, `conversations`,
`usage_counters`, `messages`, `telemetry_events`, `app_config`, and `sessions`.

Performance: missing covering indexes on `conversations.user_id` and
`messages.conversation_id`. The advisor also reports an unused
`ix_telemetry_events_event` index; it is not changed by this migration.

## Post-deployment verification

1. Verify all eight tables report RLS enabled.
2. Verify `anon` and `authenticated` lack every table and sequence privilege.
3. Verify both foreign-key index warnings are gone.
4. Verify backend health, login, conversation CRUD, message send, admin pages,
   and Alembic revision `ef56ab67bc90`.
5. Re-run Supabase security and performance advisors and append dated output.

## Rollback

Pause writes first. Run `alembic downgrade de45fa67bc89` only when restoring
the prior direct-API posture is an explicit incident decision; that downgrade
removes the two indexes, disables RLS, and restores pre-migration Supabase
default grants. If data or schema integrity is in doubt, restore the recorded
Supabase backup instead, then redeploy the last known-good backend commit.
