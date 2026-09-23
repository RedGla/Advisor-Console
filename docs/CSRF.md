# CSRF and session-origin protection

Authenticated state-changing requests (`POST`, `PUT`, `PATCH`, and `DELETE`) carrying the opaque `session_token` cookie must include an `Origin` matching `FRONTEND_URL`. A matching `Referer` origin is accepted for browsers that omit `Origin`; missing, malformed, and hostile origins are rejected with HTTP 403. Unauthenticated login, registration, health checks, and safe `GET` requests are not blocked by this middleware.

This explicit origin check is required because production may use `SameSite=None` for the cross-origin Vercel-to-backend deployment. The session token remains HttpOnly and is never exposed to JavaScript. `COOKIE_SECURE=true` is required in production.
