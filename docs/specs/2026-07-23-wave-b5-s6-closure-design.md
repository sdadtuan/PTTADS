# Design: Wave B5 S6 — Closure, SOP overdue ops banner, sign-off automation

**Date:** 2026-07-23  
**Status:** Approved  
**Parent:** [`wave-b5-dev-plan.md`](../runbooks/wave-b5-dev-plan.md) · Sprint 6 (closure)  
**Approach:** A — B5 production readiness (no Launch QA UI)

---

## 1. Decisions (PO)

| Topic | Decision |
|-------|----------|
| Scope | A — B5 Closure: pytest parity + SOP overdue ops + sign-off automation |
| FR-SD-03 | **Ops banner + list** trên `/crm/sop` — không email cron v1 |
| Launch QA | Out of scope (Wave B6) — gate warn+confirm ghi nhận cho B6 |
| Execute | Viết spec + implement |

---

## 2. Nest API

| Method | Path | Change |
|--------|------|--------|
| GET | `/api/crm/sop/overdue-tasks` | **New** — task quá hạn + run + lifecycle link |

Response: `{ overdue_enabled, total, tasks[] }` where each task has `run_id`, `run_name`, `lifecycle_id`, `due_date`, `days_overdue`, `title`, `role`, `status`.

Env `PTT_SOP_OVERDUE_ESCALATE=1` — prod sign-off; API vẫn trả data (banner luôn hiện khi có overdue).

---

## 3. UI

| Surface | Change |
|---------|--------|
| `/crm/sop` | Banner đỏ khi có overdue; bảng task quá hạn + link lifecycle |
| `LifecycleSopPanel` | Alert nhỏ khi run hiện tại có overdue |

---

## 4. Cutover / gates

| Artifact | Change |
|----------|--------|
| `wave_b5_pytest_parity.sh` | Thêm `test_crm_svc_consult_bridge.py` |
| `wave_b5_gates.py` | S6 spec + overdue module; pytest list |
| `scripts/wave_b5_signoff.sh` | **New** — gate + pytest → evidence JSON |
| `wave_b5_deploy.sh` | `PTT_SOP_OVERDUE_ESCALATE=1` |
| `wave-b5-po-signoff-checklist.md` | S6 overdue + signoff script |

---

## 5. Out of scope

- Email/cron manager digest (FR-SD-03 v2)
- Launch QA / Creative brief (Wave B6)
- Full `test_crm_svc_presales_cap_l35.py` parity (defer)
