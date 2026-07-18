# ADR-011 — Portal client auth MVP (Sprint 0)

**Status:** Accepted (Sprint 0 spike)  
**Date:** 2026-07-17  
**Context:** Phase 3 client portal needs scoped auth before Next.js UI. Keycloak full rollout is Phase 3.1.

## Decision

1. **Nest issues HS256 JWT** on `POST /api/v1/portal/auth/login`.
2. Claims: `sub`, `email`, `client_id`, `role` (`viewer` | `approver`), `exp`.
3. **MVP users:** env `PTT_PORTAL_STUB_USERS` and/or PG table `portal_client_users` (password `plain:` prefix for dev only).
4. Portal calls Nest with `Authorization: Bearer` — no Flask session on `portal.pttads.vn`.
5. Secret: `PTT_PORTAL_JWT_SECRET` (falls back to `PTT_CRM_INTERNAL_KEY` in dev only).

## Consequences

- Fast spike without Keycloak infra.
- Must rotate JWT secret on prod cutover.
- Password hashing: bcrypt required before prod portal users (stub env OK for staging).
- Internal APIs remain `X-PTT-Internal-Key`; portal JWT is separate guard.

## Phase 3.1

- Keycloak OIDC; Nest validates issuer JWKS.
- MFA for approver role.
