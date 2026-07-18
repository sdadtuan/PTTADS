# ADR-014 — Hub PG primary; SQLite Hub sunset

**Status:** Accepted (Phase 4)  
**Date:** 2026-07-17

## Decision

1. **`PTT_HUB_PG_PRIMARY=1`** — Hub campaign metadata read+write on PostgreSQL `hub_campaigns`.
2. SQLite `crm_campaigns` receives **dual-write** during Phase 4 transition only.
3. End Phase 4: SQLite Hub tables read-only; new campaigns PG-only.

## Sunset criteria

- Phase 3 hub map 100% on PG ≥ 30d
- No Flask Hub write errors 14d with PG primary
- Rollback drill documented in `hub-pg-migration.md`
