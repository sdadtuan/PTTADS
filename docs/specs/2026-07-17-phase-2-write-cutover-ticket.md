# Phase 2 ticket — CRM write cutover (PG primary)

> **Created:** Phase 1b B9 exit artifact  
> **Status:** Backlog — superseded by PRD Phase 2 Track W  
> **PRD:** [`2026-07-17-prd-phase-2.md`](2026-07-17-prd-phase-2.md)

---

## Goal

Move CRM lead **write** path from Flask/SQLite OLTP to NestJS/PostgreSQL primary, with dual-run validation on staging.

## Preconditions

- [ ] B8 read cutover stable on production (Nest PG read, dual-run 0% on staging ≥ 7 days)
- [ ] B9 staging write POC proven (`POST/PATCH /api/v1/leads` on staging)
- [ ] `LeadAssigned` outbox + RMQ publish verified on staging
- [ ] Reconcile SQLite ↔ PG green after write sync strategy defined

## Scope

| In scope | Out of scope |
|----------|--------------|
| `POST /api/v1/leads` production (Nest → PG OLTP) | Deprecate Flask monolith |
| `PATCH` assign, status update | Full AI scoring pipeline |
| Bi-directional or PG-primary sync worker | Hub/SOP PG migration |
| Flask write dual-run on staging | Write cutover on prod in Phase 1b |

## Technical tasks

1. **PG OLTP schema** — promote `crm_leads` from read replica to primary (new migrations, FK to `clients`).
2. **Sync inversion** — PG → SQLite fallback or stop SQLite writes.
3. **Nest write prod** — `PTT_LEADS_WRITE_ENABLED=1` with auth hardening.
4. **Flask strangler** — proxy legacy `/api/crm/leads/*/assign` to v1 or deprecate with UI update.
5. **Events** — `LeadAssigned`, `LeadScored` full (not stub) via RMQ consumers.
6. **Rollback** — `PTT_LEADS_WRITE_UPSTREAM=flask` flag + runbook.

## Acceptance criteria

- Assign from Agency Ops UI works via Nest on staging
- No lead loss in dual-run write soak (48h staging)
- Rollback drill documented and tested
- OpenAPI v1 write promoted from draft to frozen

## References

- `schemas/crm/leads-v1-write.openapi.yaml`
- `services/ptt-crm-api/src/leads/leads-write.service.ts`
- `docs/specs/2026-07-17-sqlite-pg-migration.md` (order #3)
- `docs/specs/events/catalog.yaml` — `LeadAssigned`

---

| Owner | Target |
|-------|--------|
| BE | Phase 2 sprint 1 |
| QA | Staging soak after B9 sign-off |
