# Wave B6-S5 — Onboarding Widget & Lifecycle ↔ Client Link

**Date:** 2026-07-23  
**Status:** PO approved  
**Depends on:** B6-S1…S4 (lifecycle bridges pattern)

## PO decisions

| Topic | Decision |
|-------|----------|
| Scope | **C_onboarding** — B6.1 widget chuyên nghiệp + link lifecycle ↔ agency client |
| Execute | **go** — spec + triển khai |

## Gap vs baseline (~70%)

| Có sẵn | Thiếu (S5) |
|--------|------------|
| Checklist PG + progress bar | Widget workflow (badge, steps, nudge/start) |
| `GET/PATCH onboarding` | Summary API gộp workflow + lifecycle links |
| Temporal `ClientOnboardingWorkflow` | Panel Onboard trên service-delivery |
| Text `Temporal workflow: {status}` | Link 2 chiều lifecycle ↔ client checklist |

## Flow

```
Contract promote → lifecycle Onboard
    ↔ agency client checklist (agency_client_id)
    → Temporal polls checklist → auto activate @ 100%
```

## API

### Agency (staff, `crm_agency`)

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/api/v1/clients/:id/onboarding/summary` | Checklist + progress + workflow + linked lifecycles |
| POST | `/api/v1/clients/:id/onboarding/nudge` | Signal `checklist_updated` |
| POST | `/api/v1/clients/:id/onboarding/start-workflow` | Start Temporal nếu chưa có |

### CRM lifecycle (`crm_board`)

| GET | `/api/crm/service-lifecycle/:id/onboarding-brief` | Client checklist snapshot + link checklist tab |

## UI

- `/agency/clients/[id]?tab=checklist` — `ClientOnboardingWidget` (timeline, workflow card, lifecycle links)
- `/crm/service-delivery/[id]` — `LifecycleOnboardingPanel` trên stage **Onboard** (banner + link client)

## Gates

- `wave_b6_gates.py` — thêm file S5
- `wave_b6_smoke.sh` — GET onboarding/summary + onboarding-brief
