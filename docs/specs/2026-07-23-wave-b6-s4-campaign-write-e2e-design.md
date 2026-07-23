# Wave B6-S4 — Campaign Write Meta E2E

**Date:** 2026-07-23  
**Status:** PO approved  
**Depends on:** B6-S1, B6-S2, B6-S3

## PO decisions

| Topic | Decision |
|-------|----------|
| Scope | **C_full** — Staff hub + lifecycle + auto-bridge + staff approve/reject |
| Auto-tick | **`on_executed`** — tick `budget_confirmed` khi Meta write `executed` |
| Approve cap | **`meta_campaign_write` approve** (GDKD/Admin Meta) |
| Submit cap | **`crm_board` edit** (AM/MKT) |
| Pilot UX | **warn_submit** — banner cảnh báo nếu ngoài pilot allowlist |

## Flow

```
Staff submit budget (CRM) → campaign_write_requests pending_approval
    → meta_campaign_write approve → Temporal → Meta Graph
    → status=executed → LaunchQaBudgetBridge → tick budget_confirmed
    → optional launch_ready if checklist complete
```

Bridge trigger: Python `mark_campaign_write_executed` → Nest `POST /api/internal/launch-qa/sync-budget-confirmed`.

## API (staff CRM)

| Method | Path | Cap | Mô tả |
|--------|------|-----|--------|
| GET | `/api/crm/campaign-writes/stats` | meta_campaign_write view | Counts + pending banner |
| GET | `/api/crm/campaign-writes?status=` | view | List + lifecycle_id |
| POST | `/api/crm/campaign-writes/submit` | crm_board edit | Submit daily_budget change |
| POST | `/api/crm/campaign-writes/:id/approve` | approve | Approve + Temporal signal |
| POST | `/api/crm/campaign-writes/:id/reject` | approve | Reject (no checklist change) |

Lifecycle:

| GET | `.../budget-brief` | TMMT budget hint + recent writes |
| POST | `.../budget-submit` | Shortcut submit from lifecycle |

Launch QA stats: `pending_campaign_writes`.

## UI

- `/crm/campaign-writes` — Campaign Write Hub
- Launch QA tab — budget form + pending banner
- Launch board banner when pending > 0
