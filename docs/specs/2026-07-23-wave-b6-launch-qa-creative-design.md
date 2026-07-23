# Wave B6 — Launch QA + Creative Brief (Service Delivery)

**Date:** 2026-07-23  
**Status:** Approved (PO)  
**Wave:** B6 (post B5 closure)

## Goal

Đưa **Launch QA checklist** và **Creative brief tối thiểu** vào Service Delivery lifecycle — staff không cần internal key / workflow console riêng.

## PO decisions

| Topic | Decision |
|-------|----------|
| Scope | Launch QA + Creative brief minimal + auto-start QA khi vào **Deliver** |
| Lifecycle link | **Lookup** `agency_client_id` (UUID PG) + `campaign.code` → `external_campaign_id` — **không** thêm cột SQLite |
| Auto-start | Khi lifecycle advance → `deliver` (idempotent theo cặp client+campaign) |
| Gate Deliver→Handover | **Warn only** — banner trên workflow, **không** block advance |
| Temporal | **PG-first** — Nest CRUD checklist; Temporal nudge optional nếu worker bật |
| Env | `PTT_LAUNCH_QA_AUTO_START_ON_DELIVER=1` (prod optional) |

> Ghi chú: phạm vi “full” ban đầu có đề cập strict block; PO đã chốt **warn_only** cho gate — implement theo warn_only.

## Architecture

```
ops-web (tab Launch QA)
    → GET/PATCH /api/crm/service-lifecycle/:id/launch-qa
    → GET/POST .../creative-brief | .../creative-submit
Nest ServiceLifecycleService
    → LaunchQaPgRepository (PG launch_qa_runs)
    → LaunchQaAutoStartService (on deliver enter)
    → CreativesService (submit staff)
    → lifecycle-launch-gate.util (advance-info banner)
```

## API (staff CRM)

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/api/crm/service-lifecycle/:id/launch-qa` | Run hiện tại (lookup client+campaign) |
| POST | `/api/crm/service-lifecycle/:id/launch-qa/start` | Manual retry auto-start |
| PATCH | `/api/crm/service-lifecycle/:id/launch-qa/checklist/:itemKey` | Toggle checklist item |
| GET | `/api/crm/service-lifecycle/:id/creative-brief` | Brief gợi ý + creatives theo campaign |
| POST | `/api/crm/service-lifecycle/:id/creative-submit` | Staff gửi creative portal |

`advance-info` bổ sung `launch_qa_gate` khi stage `deliver` và next `handover`:

```json
{
  "launch_qa_gate": {
    "ok": false,
    "warn_only": true,
    "launch_ready": false,
    "progress_percent": 50,
    "messages": ["Launch QA chưa launch_ready — xem tab Launch QA"]
  }
}
```

## Checklist (6 items — parity Python/Temporal)

- `pixel_verified`, `naming_convention`, `budget_confirmed`, `creative_approved`, `utm_tracking`, `qa_signoff`

Khi **tất cả** item `completed=true` → PG `status=passed`, `launch_ready=true` (PG-first, không cần worker).

## Auto-start idempotent

1. Resolve context: `contract.agency_client_id` + `campaign.code`
2. `SELECT ... FROM launch_qa_runs WHERE client_id AND external_campaign_id ORDER BY started_at DESC LIMIT 1`
3. Nếu có run `in_progress|passed` → reuse (idempotent)
4. Nếu không → INSERT + optional `LaunchQAWorkflow`

## UI

- Tab **Launch QA** trên `/crm/service-delivery/[id]` (deliver+)
- Panel checklist + progress + link portal creative
- Workflow banner vàng @ Deliver khi chưa `launch_ready` (warn only)

## Cutover

- `scripts/wave_b6_gate.sh`, `scripts/wave_b6_smoke.sh`
- Env example: `PTT_LAUNCH_QA_AUTO_START_ON_DELIVER=1`

## Out of scope B6

- Block cứng Deliver→Handover (deferred — PO chọn warn)
- Full creative studio / asset CDN
- Launch QA hub riêng (chỉ lifecycle tab)
