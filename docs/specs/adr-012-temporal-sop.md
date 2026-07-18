# ADR-012 — Temporal vs SOP DB for workflow gates

**Status:** Accepted (Phase 4)  
**Date:** 2026-07-17

## Decision

1. **New approval gates** (campaign write, creative, launch QA, onboarding) use **Temporal workflows** — not SOP `crm_sop_run_tasks` code conditions.
2. **Legacy SOP UI** remains for marketing checklist templates; reads PG when `PTT_SOP_READ_SOURCE=1`.
3. SOP runs **do not block** Meta API writes — Temporal workflow completion is the gate.

## Consequences

- Single observability path (Temporal UI + history).
- SOP DB gradually archival; no dual gate logic.
- AM training: approvals in Agency Ops + Temporal-linked queues.
