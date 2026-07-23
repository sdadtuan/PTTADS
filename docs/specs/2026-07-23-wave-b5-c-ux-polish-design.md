# Design: Wave B5-C — UX polish (AM/SP professional workflow)

**Date:** 2026-07-23  
**Status:** Approved  
**Parent:** [`wave-b5-dev-plan.md`](../runbooks/wave-b5-dev-plan.md) · Track C  
**Approach:** B — UI + small API enrich (no large refactor)

---

## 1. Decisions (PO)

| Topic | Decision |
|-------|----------|
| Track | C — UX polish AM/SP/GDKD |
| Kanban DnD | **Strict** — drag chỉ +1 forward khi gate pass; lùi stage trên detail |
| Staff picker | AM default = lead owner; SP gợi ý presales / task |
| P0 scope | staff picker, deep-link, hub links, finance actions, kanban filter, kanban DnD |

---

## 2. API additions

### `GET /api/crm/service-lifecycle/:id/context`

| Field | Source |
|-------|--------|
| `lifecycle_id` | row |
| `lead_id`, `customer_id`, `contract_id` | lifecycle |
| `lead.owner_id`, `lead.full_name` | crm_leads |
| `presales.assigned_sp` | crm_lead_presales |
| `contract.amount_vnd`, `contract.agency_client_id`, `contract.campaign_id` | crm_contracts |
| `campaign.name`, `campaign.code` | crm_campaigns (optional) |
| `agency_client` display | client_channel_accounts / agency clients |

### Existing APIs (wire UI)

- `PATCH .../service-lifecycle/:id` — `assigned_am`, `assigned_sp`
- `GET .../advance-info` — pre-check before kanban drop
- `POST .../expenses` — chi delivery
- `POST /api/crm/svc-payments` — thu AR

---

## 3. UI components

| Component | Surface |
|-----------|---------|
| `LifecycleStaffPicker` | lifecycle detail — AM/SP dropdown (`fetchCrmStaffList`) |
| `LifecycleHubLinksPanel` | lifecycle detail — HĐ, agency client, campaign |
| `LifecycleFinanceActions` | workflow — form chi + thu |
| `ServiceDeliveryKanban` | filter AM/slug + strict HTML5 DnD |
| `LeadContractPanel` | banner + link `/crm/service-delivery/{id}` when promoted |
| `ContractApprovalsPanel` | post-approve toast/link lifecycle |

---

## 4. Kanban strict DnD

1. User drags card from column `from_stage`
2. Drop target must be column `next_stage(from_stage)` only
3. Client calls `GET advance-info`; if `!can_advance_forward` → toast `block_reason`
4. `PATCH { stage: next }` — server re-validates gates
5. Backward: detail page only (notes + confirm)

---

## 5. Verification

- Nest unit test: context endpoint shape
- Manual UAT: PO checklist items 3–7
- `wave_b5_gate.sh` regression (no pytest change required)

---

## 6. Out of scope (P1)

- TMMT 12-field full form (Track B)
- Consult brief sidebar
- Zalo/email GDKD notify
- Drag across multiple columns skip
