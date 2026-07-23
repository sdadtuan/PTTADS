# Design: Wave B5 S4 — Finance handoff + payment gate

**Date:** 2026-07-23  
**Status:** Approved  
**Parent:** [`wave-b5-dev-plan.md`](../runbooks/wave-b5-dev-plan.md) · Sprint 4  
**Approach:** C — Balanced finance pro + payment gate warn/confirm

---

## 1. Decisions (PO)

| Topic | Decision |
|-------|----------|
| Scope | C — Tab Tài chính + gate + enrich API |
| Payment gate Handover→Retain | **Warn + confirm** — outstanding > 0 cần `finance_confirm=true` trên PATCH |
| Finance UI | Tab **Tài chính** + banner công nợ @ Handover |
| Hub promote | Đã có S0 — chỉ verify, không re-implement |

---

## 2. Nest API

| Method | Path | Change |
|--------|------|--------|
| GET | `.../finance-summary` | Thêm `ar_pending_vnd`, `ar_overdue_vnd`, `outstanding_vnd` |
| GET | `.../presales-summary` | Unchanged (expense lists) |
| GET | `.../payments` | **New** — list payments lifecycle |
| PATCH | `.../service-lifecycle/:id` | Body `finance_confirm?: boolean` cho Handover→Retain |
| GET | `.../advance-info` | Thêm `payment_gate` khi stage=handover |

---

## 3. Payment gate logic

- `outstanding_vnd = max(0, expected_revenue - received_revenue)`
- Handover → Retain:
  - outstanding = 0 → pass
  - outstanding > 0 → PATCH cần `finance_confirm: true`
  - Kanban DnD: blocked (advance-info `can_advance_forward=false`)

---

## 4. UI

| Component | Surface |
|-----------|---------|
| `LifecycleFinancePanel` | Tab **Tài chính** — KPI, presales/delivery tables, payments, forms |
| Workflow @ Handover | Banner công nợ + checkbox xác nhận trước **Chuyển → Retain** |
| `LifecycleFinanceActions` | Chuyển vào tab Tài chính (bỏ duplicate ở workflow footer) |

---

## 5. Out of scope

- Strict pytest parity toàn bộ `test_crm_svc_finance_presales_on_lead.py`
- Hub ContractActivated hook (S0 done)
- Dedicated `GET /funnel-stats` route (list API đủ)
