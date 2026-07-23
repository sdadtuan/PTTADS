# Design: Wave B5 S3 — TMMT R5 + Consult bridge

**Date:** 2026-07-23  
**Status:** Approved  
**Parent:** [`wave-b5-dev-plan.md`](../runbooks/wave-b5-dev-plan.md) · Sprint 3  
**Approach:** C — Balanced (TMMT form R5 + consult brief + prefill; Deliver gate unchanged)

---

## 1. Decisions (PO)

| Topic | Decision |
|-------|----------|
| Scope | C — Cân bằng spec + UX chuyên nghiệp |
| TMMT UI | Tab riêng **TMMT chính thức** trên lifecycle detail |
| Consult prefill | **Auto** khi advance → Consult (giống Python) + nút thủ công `overwrite` |
| Deliver gate | Giữ `validateOfficialTmmt` hiện tại (Onboard → Deliver) |
| Consult advance gate | **Không** block lifecycle Lead→Consult (chỉ brief hiển thị warn/block level) |

---

## 2. Nest API

### Marketing plan (extend)

| Method | Path | Change |
|--------|------|--------|
| GET | `.../marketing-plan` | Payload R5: `strategy_framework`, `target_market_prof`, `tmmt_core_keys`, `filled_count` |
| PATCH | `.../marketing-plan` | Merge `target_market_prof` / `strategy_framework` objects |
| GET | `.../marketing-plan/validation` | Unchanged |

### Consult bridge (new)

| Method | Path | Hành vi |
|--------|------|---------|
| GET | `.../consult-brief` | Aggregate lead task, intake, readiness, recommended actions |
| POST | `.../consult-prefill` | Body `{ overwrite?: boolean }` — prefill consult task form |

### Stage advance hook

`PATCH .../service-lifecycle/:id` with `stage: consult` → auto `prefillConsultTask(overwrite=false)` after advance.

---

## 3. UI

| Component | Surface |
|-----------|---------|
| `LifecycleTmmtPanel` | Detail tab **TMMT chính thức** — 12 prof fields + strategy keys, progress N/12, gate banner |
| `ConsultBriefPanel` | Workflow tab **Consult** — readiness, highlights, intake summary, prefill button |
| Workflow (onboard) | Compact TMMT gate banner + link sang tab TMMT |
| `ServiceDeliveryWorkflowPanel` | Bỏ textarea TMMT inline (chuyển sang tab riêng) |

---

## 4. Verification

- Jest: `lifecycle-marketing-plan.util`, `lifecycle-consult.util`
- Nest build + ops-web build
- Manual UAT: §11 công đoạn 9 (gate TMMT), consult prefill on advance

---

## 5. Out of scope

- Strict pytest parity toàn bộ `test_crm_svc_consult_bridge.py`
- Diff view sơ bộ vs chính thức TMMT
- Consult soft gate block Lead→Consult on lifecycle PATCH
- Sticky header gate banner (chọn tab TMMT riêng thay vì sticky)
