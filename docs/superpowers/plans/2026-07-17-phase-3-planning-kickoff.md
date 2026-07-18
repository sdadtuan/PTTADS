# Phase 3 Planning Kickoff

> **For agentic workers:** Planning doc only — implementation plans per track will follow after stakeholder sign-off on PRD v1.0.

**Goal:** Align squad on Phase 3 scope, gates, timeline, and first executable spikes.

**Architecture:** Client Portal (Next.js) + Temporal workflows on existing Nest/PG stack; Google Ads adapter; Hub/SOP PG migration. Flask retained for internal ops.

**Tech Stack:** Next.js 14, NestJS, Temporal, PostgreSQL, Python worker, existing Meta closed-loop modules.

## Global Constraints

- Phase 2 DoD §10 must pass before prod portal launch.
- W5 prod `POST /api/v1/leads` = Phase 2.1 bridge, not blocking portal read MVP.
- No Flask monolith deprecation in Phase 3 (Phase 4).
- Portal tenant isolation: strict `client_id` scope on every API call.
- Reuse `daily_performance` / `hub_campaign_map` — no parallel reporting DB.

---

## Planning checklist (Week 0)

### Stakeholder

- [ ] Review PRD [`2026-07-17-prd-phase-3.md`](../../specs/2026-07-17-prd-phase-3.md)
- [ ] Confirm Phase 2.1 bridge in scope (W5 + AUTH spike)
- [ ] Pick ≥3 portal pilot clients (overlap closed-loop pilots)
- [ ] Confirm Temporal: self-host VPS vs Temporal Cloud budget

### Engineering

- [ ] Architecture review [`2026-07-17-architecture-phase-3.md`](../../specs/2026-07-17-architecture-phase-3.md)
- [ ] Draft ADR-011 (portal auth MVP)
- [ ] Spike: Temporal `docker compose` + hello workflow (2 days)
- [x] Spike: Next.js `portal-web` in `services/portal-web/` — login + dashboard placeholder
- [ ] Fix ROAS `value_numeric` NOT NULL for portal column (Phase 2 debt)

### Ops / DevOps

- [ ] DNS `portal.pttads.vn` staging
- [ ] TLS cert plan (same as api.pttads.vn)
- [ ] Sentry project `ptt-portal` stub

### QA

- [ ] Extend regression matrix: portal E2E test IDs P-UAT-01–10
- [ ] Cross-tenant security test plan

---

## Track ownership (proposed)

| Track | DRI | Weeks |
|-------|-----|-------|
| P Portal | FE + Nest BE | 1–8, 13–14 |
| T Temporal | BE + DevOps | 1–8 |
| G Google | BE (mirror Meta) | 9–10 |
| D Migration | BE + DevOps | 11–12 |
| 2.1 Bridge | BE | 0 |

---

## Immediate next artifacts (ordered)

1. `docs/specs/adr-011-portal-auth.md` — JWT vs Keycloak decision
2. `docs/SPEC_UI_UX_CLIENT_PORTAL.md` — wireframes 3 pages
3. `docs/specs/workflows/client-onboarding.md` — Temporal spec
4. `services/portal-web/` — ✅ Next.js spike (login + dashboard)
5. `docker-compose.yml` — add temporal + temporal-ui services

---

## Decision log (fill in kickoff meeting)

| # | Question | Options | Decision |
|---|----------|---------|----------|
| D1 | Portal auth MVP | Nest JWT / Keycloak day-1 | TBD |
| D2 | Temporal hosting | VPS self-host / Temporal Cloud | TBD |
| D3 | Phase 2.1 sprint 0 | Yes / parallel with portal design | TBD |
| D4 | Google pilot clients | Same 3 as Meta / separate | TBD |
| D5 | Hub migration | Week 11 / defer Phase 3.1 | TBD |

---

## Success criteria for "Planning complete"

- [ ] PRD v1.0 reviewed — no open P0 scope questions
- [ ] Architecture v1.0 reviewed
- [ ] D1–D5 decisions recorded
- [ ] Sprint 0 backlog created (AUTH spike + W5 + ROAS fix)
- [ ] Phase 2 ops gates tracked to completion (parallel)

---

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-17 | Planning kickoff |
