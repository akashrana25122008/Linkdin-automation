# Security Audit (M13)

Audited: M0–M12 on master. Method: code inspection + targeted probes, no assumed safety.

## Findings fixed

### F1 — CORS blocked PATCH/PUT/DELETE (High)
- Location: `backend/app/main.py` (`allow_methods`).
- Evidence: preflight `OPTIONS` with `Access-Control-Request-Method: PATCH/PUT/DELETE` returned 400, so browsers silently blocked every frontend mutation (Studio save, Drafts delete/status, Strategy save, LinkedIn disconnect).
- Fix: allow `GET, POST, PUT, PATCH, DELETE, OPTIONS` for the configured frontend origin only. No CSRF regression: cookies remain `SameSite=Lax`, origin allowlist unchanged.
- Verification: `tests/test_security.py::test_cors_preflight_allows_mutation_methods`.

### F2 — Mock connect could overwrite a real credential (Low)
- Location: `backend/app/linkedin_oauth.py::mock_connect`.
- Evidence: flipping `LINKEDIN_MODE` to mock with an existing real row replaced the encrypted token with `""`.
- Fix: 409 `real_account_exists` when a non-mock row exists.
- Verification: `tests/test_security.py::test_mock_connect_refuses_to_overwrite_real_account`.

## Audited — PASS (with test evidence)

- Authentication: session-cookie identity, 401 on all protected routes (`test_auth`, `test_health`, per-module 401 tests).
- Authorization/user isolation: every `user_id` derives from the session; no frontend-supplied IDs; cross-user 404s tested per module (drafts, research, calendar, publishing, strategy, analytics, learning, LinkedIn).
- Google OAuth: state cookie validated, cancel/missing-code handled, ID token verified server-side with audience check, secrets backend-only.
- LinkedIn OAuth: DB-backed single-use 10-minute user-bound states, server-side exchange, Fernet-encrypted storage, key-missing refuses instead of plaintext, disconnect purges states, reconnect updates one row.
- Sessions/cookies: 256-bit tokens, SHA-256 hashes stored, 7-day expiry, HttpOnly + SameSite=Lax, Secure in production, logout revokes.
- Publishing safety: approval gate, ownership + scope checks, no duplicate publish, timeout honesty, mock never calls LinkedIn.
- Input validation: bounded strings, enum whitelists, ISO/timezone validation, bounded ranges/limits; safe 4xx codes, no stack traces (no `print`/`logging` in app code, FastAPI debug off).
- Secrets: `.env` git-ignored and never committed; history scan shows test fixtures only; frontend holds only `VITE_API_URL`; no tokens in responses, logs, or localStorage (only a UI collapse preference).
- Error handling: fixed detail codes; no secret-bearing messages.

## Accepted limitations (not vulnerabilities)

- No rate limiting: no password auth exists; OAuth states are single-use expiring 256-bit values and sessions are 256-bit tokens, so brute force is infeasible in this local-dev scope. Revisit if exposed publicly.
- `APP_SECRET_KEY` is configured but unused: sessions are opaque server-side tokens, which need no signing.
- No account/data self-deletion endpoint yet (PRD lists it as "where implemented"); deferred, tracked for M14+.
- Sessions accumulate until expiry; logout revokes the current session only.
- Expired LinkedIn tokens are handled via upstream failure, not proactive refusal.
- `Secure` cookies require `APP_ENV=production` (correct for local HTTP).

## Production requirements

Serve the backend over HTTPS with `APP_ENV=production`, set real OAuth credentials plus `LINKEDIN_TOKEN_ENCRYPTION_KEY` (Fernet key), keep `LINKEDIN_MODE` out of mock, and re-verify the LinkedIn flow against real credentials before M14 sign-off.
