# Lead Pre-sales → Lifecycle on Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Pre-sales (Lead/Consult/Proposal) trên CRM Lead; KH + Lifecycle chỉ khi ký HĐ; Lifecycle bắt đầu Onboard với 3 bước đầu đã hoàn thành.

**Architecture:** Module `crm_lead_presales` (bảng presales + tasks) tách khỏi `crm_service_lifecycle` cho đến khi `promote_presales_to_lifecycle()` chạy lúc HĐ active. Feature flag `PTT_PRESALES_ON_LEAD=1`.

**Tech Stack:** Flask 3, SQLite, existing `crm_svc_workflow_steps` task definitions.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-02-lead-presales-then-lifecycle-design.md`
- KH chỉ tạo khi `crm_contracts.status=active`
- Hỏi user trước khi mở rộng scope (contract nullable, UI lớn, migration legacy)

---

## Phase P1 — Schema + API + flag (this session)

- [ ] `crm_lead_presales.py` — schema, seed tasks (lead/consult/proposal), advance, promote stub
- [ ] `tests/test_crm_lead_presales.py`
- [ ] Wire `ensure_schema` in `app.py` init
- [ ] API: GET/POST/PATCH presales + task PATCH
- [ ] `PTT_PRESALES_ON_LEAD` — tắt AI draft lifecycle trong `crm_ai_qualify.py`
- [ ] Expose flag in lead API meta for UI (P2)

## Phase P2 — UI CRM Lead (checkpoint)

- [ ] Panel 3 tab Lead/Consult/Proposal trên `crm_leads.html` + JS
- [ ] Intake entry qua `lead_id` (không lifecycle)
- [ ] Consult brief adapter (presales_id) — **hỏi user nếu bridge phức tạp**

## Phase P3 — Contract hook (checkpoint)

- [ ] `crm_contracts.lead_id` + nullable `customer_id` migration — **hỏi user trước rebuild table**
- [ ] `on_contract_signed()` → convert + promote
- [ ] Service Delivery: ẩn presales-only deals

## Phase P4 — Legacy + docs

- [x] Backfill script `scripts/backfill_draft_lifecycle_to_presales.py` + `crm_lead_presales_legacy.py`
- [x] Update `docs/crm/README.md`
- [x] Pilot checklist `docs/crm/presales-on-lead-pilot-checklist.md`
