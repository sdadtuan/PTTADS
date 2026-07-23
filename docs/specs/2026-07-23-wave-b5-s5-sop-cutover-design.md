# Design: Wave B5 S5 — SOP Launch panel + idempotent auto-start + cutover

**Date:** 2026-07-23  
**Status:** Approved  
**Parent:** [`wave-b5-dev-plan.md`](../runbooks/wave-b5-dev-plan.md) · Sprint 5  
**Approach:** C — SOP panel + lifecycle_once auto-start + gate/deploy/smoke + env

---

## 1. Decisions (PO)

| Topic | Decision |
|-------|----------|
| Scope | C — Tab SOP Launch + idempotent auto-start + gate/deploy/smoke |
| SOP auto-start | **lifecycle_once** — một lifecycle → một SOP run; lưu `sop_run_id` trên lifecycle |
| SOP UI | Tab **SOP Launch** trên lifecycle detail (cạnh Workflow \| TMMT \| Tài chính) |
| Env | `PTT_SOP_AUTO_START_ON_LAUNCH=1` (optional prod) |
| Cutover | `PTT_FLASK_CRM_SERVICE_LIFECYCLE_RETIRED=1` trong deploy block |

---

## 2. Schema

| Table | Column | Purpose |
|-------|--------|---------|
| `crm_service_lifecycle` | `sop_run_id INTEGER` | FK logic tới `crm_sop_runs.id` |

Migration: Nest `leads-contract-sqlite.repository` ensureSchema + Flask `crm_service_lifecycle.py`.

---

## 3. Nest API

| Method | Path | Change |
|--------|------|--------|
| GET | `.../service-lifecycle/:id/sop` | **New** — run + tasks + auto-start status |
| POST | `.../contracts/approvals/:id/approve` | Response `sop_auto_start` idempotent (`run_id`, `idempotent`) |

**Auto-start (`SopAutoStartService.maybeStartOnLifecyclePromote`):**

1. Env off → `{ started: false, reason: 'disabled' }`
2. Lifecycle đã có `sop_run_id` + run còn tồn tại → `{ started: true, run_id, idempotent: true }`
3. Template `MKT-LAUNCH-14D` missing → `{ started: false, reason }`
4. Else create run, persist `sop_run_id`, return `{ started: true, run_id }`

---

## 4. UI

| Component | Surface |
|-----------|---------|
| `LifecycleSopPanel` | Tab **SOP Launch** — run KPI, task checklist, link `/crm/sop` |
| `ContractApprovalsPanel` | Sau duyệt HĐ — hiện SOP run link nếu auto-start OK |
| Lifecycle detail tabs | Workflow \| TMMT \| Tài chính \| **SOP Launch** |

---

## 5. Cutover / gates

| Artifact | Change |
|----------|--------|
| `ptt_crm/wave_b5_gates.py` | S3/S4/S5 module files; jest pattern + `LifecycleSopPanel` |
| `scripts/wave_b5_smoke.sh` | **New** — lifecycle `/sop` + SOP routes smoke |
| `scripts/wave_b5_deploy.sh` | Thêm `PTT_FLASK_CRM_SERVICE_LIFECYCLE_RETIRED=1` |

---

## 6. Out of scope

- N5.3 cron SOP overdue → email (FR-SD-03)
- PATCH task status trên SOP run từ lifecycle tab (dùng `/crm/sop` hub)
- Strict pytest cho toàn bộ SOP engine
