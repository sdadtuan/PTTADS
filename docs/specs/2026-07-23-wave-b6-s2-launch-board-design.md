# Wave B6-S2 — Launch QA Board + Confirm Gate

**Date:** 2026-07-23  
**Status:** PO approved  
**Depends on:** B6-S1 (`ba02899`)

## PO decisions

| Topic | Decision |
|-------|----------|
| Scope | Launch board hub + gate **warn + checkbox confirm** (parity Payment gate) |
| Board default | All status + filter tabs: in_progress / passed / failed / blocked / timeout |
| Lifecycle link | Reverse lookup SQLite `agency_client_id` + `campaign.code` → `lifecycle_id` |
| Gate | Deliver→Handover: block until confirm if chưa `launch_ready` |

## API

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/api/crm/launch-qa/runs?status=` | List runs + progress + lifecycle_id |
| GET | `/api/crm/launch-qa/stats` | Counts by status |

`advance-info.launch_qa_gate` bổ sung `requires_confirm`, `progress_completed`, `progress_total`.

`PATCH service-lifecycle` body: `launch_qa_confirm: true` (Deliver→Handover).

## UI

- `/crm/launch-qa` — Launch board (stats, tabs, table, links)
- OpsNav: "Launch QA" under CRM Marketing
- Workflow Deliver: checkbox confirm giống Payment gate

## Cutover

- Update `wave_b6_gate.sh` / smoke for hub routes
