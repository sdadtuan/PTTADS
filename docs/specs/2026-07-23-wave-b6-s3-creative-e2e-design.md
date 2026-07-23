# Wave B6-S3 — Creative Approval E2E

**Date:** 2026-07-23  
**Status:** PO approved  
**Depends on:** B6-S1, B6-S2

## PO decisions

| Topic | Decision |
|-------|----------|
| Scope | Auto-bridge + Staff Creative Hub + resubmit v2 + Launch board banner pending |
| Auto-tick | Portal **approve** → tick `creative_approved`; nếu 6/6 → `launch_ready` (PG logic hiện có) |
| Reject | **Không** đổi tick — chỉ cập nhật UI brief/status |
| Staff submit | Hub `/crm/creatives` + lifecycle tab (staff JWT) |
| Resubmit | Reject → MKT gửi version+1 từ hub hoặc lifecycle |

## Flow

```
Staff submit (CRM) → creative_submissions pending_client
    → Portal approve → CreativeApproved event
    → LaunchQaCreativeBridge → tick creative_approved on launch_qa_runs
    → optional launch_ready if checklist complete
```

## API (staff CRM)

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/api/crm/creatives?status=` | List creatives + lifecycle_id |
| GET | `/api/crm/creatives/stats` | pending / approved / rejected counts |
| POST | `/api/crm/creatives/submit` | Staff submit (reuse CreativesService) |

Launch QA stats bổ sung `pending_creatives` cho banner board.

## UI

- `/crm/creatives` — Creative Hub (filter, submit, resubmit vN+1)
- Launch board banner khi `pending_creatives > 0`
- Lifecycle Launch QA tab: link hub + resubmit rejected
