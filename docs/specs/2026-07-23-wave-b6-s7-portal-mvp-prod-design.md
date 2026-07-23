# Wave B6-S7 — Portal MVP production (`portal.pttads.vn`)

> **PO scope:** C_full_prod · auth_dual · perf_table · cr_history · nav_mvp · **go**

## Goal

Harden Track P Client Portal for production cutover: JWT session refresh, dual auth doc, professional performance/creative UX, client branding settings, email notify stub, Sentry, cross-tenant gate, Wave B6 module checks.

## In scope

| Area | Deliverable |
|------|-------------|
| Auth | `POST /api/v1/portal/auth/refresh`, refresh JWT, Next middleware cookie gate, token expiry banner |
| Auth prod | `PTT_PORTAL_AUTH_MODE=dual` documented in deploy env |
| Performance | KPI cards + CPL delta emphasis, empty states, `GET /performance/export.csv`, PDF stub |
| Creatives | Asset preview, confirm dialog, `GET /creatives/history?days=30`, pending badge in nav |
| Settings | `portal_client_settings` + `GET/PATCH /api/v1/portal/settings`, `/settings` page |
| Notify | AM `notification_inbox` + optional email webhook on approve/reject |
| Nav | MVP only: Performance (dashboard/meta/google) + Creative inbox + Settings |
| Observability | Optional `NEXT_PUBLIC_SENTRY_DSN` client reporter |
| QA | Cross-tenant 403 gate, Playwright history tab, wave_b6_gates S7 files |

## Out of scope (Phase 4+)

- Keycloak MFA prod cutover execution
- Full `@sentry/nextjs` source maps pipeline
- Real SMTP / PDF rendering engine

## Env

| Variable | Purpose |
|----------|---------|
| `PTT_PORTAL_AUTH_MODE=dual` | Keycloak JWKS + Nest JWT fallback |
| `PTT_PORTAL_REFRESH_TTL_SEC` | Refresh token TTL (default 30d) |
| `PTT_PORTAL_EMAIL_NOTIFY=1` | Enable email webhook on creative decision |
| `PTT_PORTAL_EMAIL_WEBHOOK_URL` | POST JSON payload (stub-friendly) |
| `NEXT_PUBLIC_SENTRY_DSN` | Portal client error reporting |

## Deploy

Same-origin `portal.pttads.vn` per `deploy/nginx-portal.conf`. After pull: rebuild Nest + portal-web, run `phase3_portal_mvp_gate.sh` + `wave_b6_gate.sh`.
