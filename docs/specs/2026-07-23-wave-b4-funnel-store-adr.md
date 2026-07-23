# ADR: Wave B4 — Lead funnel store strategy

**Date:** 2026-07-23  
**Status:** Accepted

## Context

Wave B4 ports B2 care gate, GDKD review queue, and presales from Flask/Python to Nest + ops-web. Lead core CRUD is already PG-primary (`/api/v1/leads`); funnel state (care stages, `meta_json.review_queue`, presales tables) still lives in SQLite `ptt.db`.

## Decision

Use **SQLite bridge (read-write)** for Wave B4 funnel modules — same pattern as `intake/` and `cases/` — until PG DDL for presales + funnel columns is applied in a later cutover sprint.

| Data | Store | API prefix |
|------|-------|------------|
| Lead list/get/create/patch (identity) | PostgreSQL | `/api/v1/leads` |
| Care pipeline, review queue, presales | SQLite | `/api/v1/leads/:id/care-*`, `/review-queue`, `/presales` |

## Consequences

- Nest opens `AppConfigService.sqlitePath` read-write for funnel repos.
- ops-web calls Nest v1 funnel routes (not Flask).
- `PTT_CRM_LEADS_FUNNEL_NEST=1` gates new routes; `PTT_PRESALES_ON_LEAD=1` required for presales mutations.
- PG migration (S0 DDL) deferred — documented in [`wave-b4-crm-lead-funnel-dev-plan.md`](../runbooks/wave-b4-crm-lead-funnel-dev-plan.md) Sprint 0.
