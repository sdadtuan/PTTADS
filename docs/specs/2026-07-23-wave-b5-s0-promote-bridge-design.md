# Design: Wave B5 S0 — Promote bridge (HĐ → Lifecycle)

**Date:** 2026-07-23  
**Status:** Approved · implementing  
**Parent:** [`wave-b5-dev-plan.md`](../runbooks/wave-b5-dev-plan.md) Sprint 0

---

## 1. Decisions (PO)

| Topic | Decision |
|-------|----------|
| Entry points | Lead panel + Hub inbox GDKD + Agency client tab |
| Sign flow | AM submit → `crm_contract_approvals` pending → GDKD approve → Active + promote |
| Data model | Separate `crm_contract_approvals` + `crm_contract_events` |
| Store | SQLite bridge (same ADR as Wave B4) |
| Upgrade | Readiness checklist API; seed onboard+ tasks after promote (fix Python seed skip) |

---

## 2. Schema

### `crm_contract_approvals`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| contract_id | INTEGER FK | `crm_contracts.id` |
| lead_id | INTEGER | denormalized |
| status | TEXT | `pending`, `approved`, `rejected` |
| requested_by | TEXT | staff email |
| decided_by | TEXT | GDKD email |
| amount_vnd | INTEGER | snapshot at submit |
| notes | TEXT | AM request notes |
| decision_notes | TEXT | GDKD reject reason |
| created_at | TEXT | |
| decided_at | TEXT | |

### `crm_contract_events`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| contract_id | INTEGER | |
| event_type | TEXT | `draft_created`, `submitted`, `approved`, `rejected`, `activated`, `promoted` |
| actor | TEXT | |
| payload_json | TEXT | optional |
| created_at | TEXT | |

### Migrations on existing tables

- `crm_contracts`: `lead_id`, `service_slug`, `agency_client_id`, `billing_type` (ALTER IF NOT EXISTS)
- `crm_customers`: `is_placeholder`, `placeholder_lead_id`
- `crm_marketing_plans`: `lifecycle_id`, `source_plan_id` (if missing)
- `crm_svc_tasks`, `crm_service_lifecycle`, `crm_service_lifecycle_events` — ensure exist

---

## 3. API

### Lead-scoped (`LeadsContractController`)

| Method | Path | Cap |
|--------|------|-----|
| GET | `/api/v1/leads/:id/contract/readiness` | view |
| GET | `/api/v1/leads/:id/contract` | view |
| POST | `/api/v1/leads/:id/contract` | edit |
| PATCH | `/api/v1/leads/:id/contract/:contractId` | edit |
| POST | `/api/v1/leads/:id/contract/:contractId/submit` | edit |

### Approvals (`ContractsApprovalController`)

| Method | Path | Cap |
|--------|------|-----|
| GET | `/api/v1/contracts/approvals/pending` | assign (GDKD) |
| POST | `/api/v1/contracts/approvals/:id/approve` | assign |
| POST | `/api/v1/contracts/approvals/:id/reject` | assign |

### Agency (`AgencyContractsController`)

| Method | Path |
|--------|------|
| GET | `/api/v1/agency/clients/:clientId/contracts` |

### Env

- `PTT_CRM_SERVICE_DELIVERY_NEST=1` — enable module
- Requires `PTT_CRM_LEADS_FUNNEL_NEST=1` + `PTT_PRESALES_ON_LEAD=1`

---

## 4. Promote pipeline (on approve)

1. Validate presales stages complete + preliminary marketing plan
2. `convertLeadToCrm()` — real customer + case
3. Update contract `customer_id`, `status=active`, `signed_on`
4. `promotePresalesToLifecycle()` — lifecycle onboard, copy tasks, seed post-onboard stages, clone TMMT
5. Lead `status=won`; delete placeholder customer if orphan
6. Log contract events + lead activity

---

## 5. Readiness checklist

| Key | Rule |
|-----|------|
| `b2_complete` | presales_care_gate |
| `presales_stages` | lead/consult/proposal 100% tasks |
| `marketing_plan` | validatePreliminaryPlan ok |
| `contract_draft` | draft exists |
| `no_pending_approval` | no other pending approval for contract |

---

## 6. UI

| Surface | Component |
|---------|-----------|
| `/crm/leads/[id]` | `LeadContractPanel` |
| `/crm/hub` | Tab **HĐ chờ duyệt** + existing campaign map |
| `/agency/clients/[id]` | Tab contracts list |

---

## 7. Tests

- Nest unit: readiness, promote idempotency, approval state machine
- Parity: run `pytest tests/test_crm_lead_presales_contract.py` after Nest promote matches (manual gate)

---

## 8. Out of scope S0

- SOP auto-start (S5)
- Full kanban / task UI (S1–S2)
- PG cutover
