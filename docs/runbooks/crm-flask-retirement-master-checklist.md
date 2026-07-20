# CRM Flask retirement — Master checklist

> **Mục tiêu:** Toàn bộ CRM staff + API không còn phụ thuộc Flask (`ptt.service`).  
> **Thực tế hiện tại:** **100%** module **RETIRED** · **Flask HTTP removed from repo** · **`can_stop_ptt_service: true`**.

**Quyết định điều hành:** [`SPEC_MIGRATION_FLASK_EXECUTION_PLAN.md`](../SPEC_MIGRATION_FLASK_EXECUTION_PLAN.md) — strangler 12 tháng, không big-bang.

---

## Trạng thái nhanh

```bash
./scripts/crm_flask_migration_pack.sh gap      # % migrated + blockers
./scripts/crm_flask_migration_pack.sh wave8    # Flask HTTP removed gates
./scripts/crm_flask_migration_pack.sh phase5-dry  # stop Flask dry-run
```

| Trạng thái | Chi tiết |
|------------|----------|
| **Registry** | 22/22 module `RETIRED` (email greenfield) |
| **Flask HTTP** | `app.py` + `blueprints/` + `templates/` + `static/` removed · Nest `:3000` canonical |
| **Public site** | Landing/CMS marketing site removed — web-app only (`ops.pttads.vn`, `portal.pttads.vn`) |
| **Cron** | owner-weekly, finance KPI, FB sync → Nest `/api/crm/*` |
| **systemd** | workers depend on `ptt-crm-api.service`, not `ptt.service` |

**ops-web CRM:** full module set on `ops.pttads.vn/crm/*` · **Nest CRM:** all modules on `:3000/api/crm/*`

---

## Nguyên tắc

1. **Migrate từng module** — Nest API + ops-web UI + nginx redirect + Flask readonly
2. **Không tắt `ptt.service`** cho đến khi `gap_report.can_stop_ptt_service = true`
3. **Python workers giữ** — `ptt_worker`, `ptt-fb-autosync`, `ptt_temporal` ≠ Flask HTTP
4. **PG primary** cho lead OLTP; SQLite `ptt.db` shadow dần bỏ

---

## Wave 0 — Đóng cutover đã làm (1–2 tuần) ✅ checklist

- [ ] **W0-1** Env: `deploy/env.crm-flask-migration.example` → VPS `.env`
- [ ] **W0-2** `PTT_LEADS_*_SOURCE=pg`, `PTT_AGENCY_OPS_UPSTREAM=ops-web`
- [ ] **W0-3** Horizon 0: SEO + Email admin retire ([`horizon0-gate-a-execution.md`](./horizon0-gate-a-execution.md))
- [ ] **W0-4** Horizon 1: Meta hub + webhook Nest ([`horizon1-meta-ads-migration-checklist.md`](./horizon1-meta-ads-migration-checklist.md))
- [ ] **W0-5** nginx: `deploy/nginx-rs-delivery-admin-retired.conf`
- [ ] **W0-6** `./scripts/crm_flask_migration_pack.sh wave0` → PASS

---

## Wave 1 — Leads parity + Catalog (Tháng 1)

**Blocker lớn nhất hàng ngày:** staff dùng Flask `/crm/leads` legacy features.

| # | Deliverable | Flask retire |
|---|-------------|--------------|
| 1.1 | Nest: port `/api/crm/leads/*` (assign, activities, audit) | readonly | ✅ (1b) |
| 1.2 | ops-web: enrich `/crm/leads/[id]` | — | ✅ (1b) |
| 1.3 | Nest: **`catalog/`** module (services, industries, assign-scopes) | `/crm/catalog` redirect | ✅ |
| 1.4 | ops-web: `/crm/catalog` | — | ✅ |
| 1.5 | nginx: `/crm/catalog` → ops-web; `/crm/leads` → ops-web | — | ✅ |
| 1.6 | Soak 7d staff leads trên ops-web | — | timer + bootstrap staging |

**DoD Wave 1 catalog:** `./scripts/wave1_catalog_gate.sh` PASS · env `PTT_FLASK_CRM_CATALOG_RETIRED=1`

**DoD Wave 1b leads legacy:** `./scripts/wave1b_leads_gate.sh` PASS · env `PTT_FLASK_CRM_LEADS_LEGACY_RETIRED=1`

**DoD Wave 1 full:** `./scripts/wave1_full_pack.sh full` (staging) hoặc `./scripts/wave1_full_gate.sh` + soak 7d prod · env `PTT_FLASK_CRM_LEADS_UI_RETIRED=1` · presales/AI/import API vẫn Flask

```bash
# Preflight (local/VPS)
./scripts/wave1_full_gate.sh

# Staging sign-off (bootstrap 7d soak — KHÔNG prod)
./scripts/wave1_full_pack.sh full

# Prod soak (daily cron)
# deploy/ptt-wave1-leads-soak.timer
./scripts/wave1_leads_soak_record.sh
```

---

## Wave 2 — Customers + Intake (Tháng 2)

| Module | Nest | ops-web | Flask retire |
|--------|------|---------|--------------|
| Customers | `customers/` ✅ | `/crm/customers`, `/[id]` ✅ | readonly |
| Intake | `intake/` ✅ | `/crm/intake` ✅ | readonly |
| Cases | `cases/` ✅ | API Nest (board HTML Flask) | readonly API ✅ |

**DoD Wave 2:** `./scripts/wave2_gate.sh` PASS · env `PTT_FLASK_CRM_CUSTOMERS_RETIRED=1` · `PTT_FLASK_CRM_INTAKE_RETIRED=1`

```bash
./scripts/wave2_gate.sh
# hoặc
./scripts/crm_flask_migration_pack.sh wave2
```

**Còn Flask (Wave 2+):** customer brief AI, lifecycle HTML, relations/purchases/issues writes, intake AI summary/reopen/stats.

**DoD Wave 2+:** `./scripts/wave2_plus_gate.sh` PASS · env `PTT_FLASK_CRM_CASES_RETIRED=1`

```bash
./scripts/wave2_plus_gate.sh
```

**Còn Flask sau Wave 2+:** customer lifecycle HTML, brief AI thật (Anthropic), intake AI Claude, CRM board HTML `/crm`.

---

## Wave 3 — Service ops (Tháng 3–4)

| Module | Nest | ops-web | Flask retire |
|--------|------|---------|--------------|
| Marketing plans | `marketing-plans/` ✅ | `/crm/marketing-plan` ✅ | readonly |
| Service lifecycle | `service-lifecycle/` ✅ | `/crm/service-delivery` ✅ | readonly |
| SOP | `sop/` ✅ | `/crm/sop` ✅ | readonly |

**DoD Wave 3:** `./scripts/wave3_gate.sh` PASS · env `PTT_FLASK_CRM_MARKETING_PLANS_RETIRED=1` · `PTT_FLASK_CRM_SERVICE_LIFECYCLE_RETIRED=1` · `PTT_FLASK_CRM_SOP_RETIRED=1`

```bash
./scripts/wave3_gate.sh
# hoặc
./scripts/crm_flask_migration_pack.sh wave3
```

**Còn Flask sau Wave 3:** marketing segment refs, lifecycle workflow tasks/presales gates, SOP step editor, milestones/campaigns linking.

---

## Wave 3 (legacy table)

| Module | Routes (approx) |
|--------|-----------------|
| Marketing plans | 8 + presales blueprint |
| Service lifecycle | 30+ |
| SOP | 18 |

Nest modules: `marketing-plans/`, `service-lifecycle/`, `sop/`  
ops-web: `/crm/marketing-plan`, `/crm/service-delivery`, `/crm/sop`

---

## Wave 4 — Sales + KPI + Staff (Tháng 4–5)

| Module | Nest | ops-web | Flask retire |
|--------|------|---------|--------------|
| Sales | `sales/` ✅ | `/crm/sales` ✅ | readonly |
| KPI | `kpi/` ✅ | `/crm/kpi`, `/crm/staff-kpi` ✅ | readonly |
| Staff | `crm-staff/` ✅ | `/crm/staff` ✅ | readonly |

**DoD Wave 4:** `./scripts/wave4_gate.sh` PASS · env `PTT_FLASK_CRM_SALES_RETIRED=1` · `PTT_FLASK_CRM_KPI_RETIRED=1` · `PTT_FLASK_CRM_STAFF_RETIRED=1`

```bash
./scripts/wave4_gate.sh
# hoặc
./scripts/crm_flask_migration_pack.sh wave4
```

**Còn Flask sau Wave 4:** sales deals HTML, KPI board HTML, proposals matrix editor, payroll full UI.

---

## Wave 4+ — Sales extended + Proposals + Payroll dashboard

| Module | Nest | ops-web | Flask retire |
|--------|------|---------|--------------|
| Sales extended | `sales/` pipeline/partners/trainings/market/reports ✅ | `/crm/sales` tabs ✅ | readonly |
| KPI extended | `kpi/` alerts/chart + `staff/kpi` export/progress ✅ | `/crm/kpi` ✅ | readonly |
| Staff extended | `crm-staff/` import/levels/competency ✅ | `/crm/staff` tabs ✅ | readonly |
| Proposals | `proposals/` ✅ | `/crm/proposals` ✅ | readonly |
| Payroll | `payroll/` dashboard MVP ✅ | — | HTML Flask |

**DoD Wave 4+:** `./scripts/wave4_plus_gate.sh` PASS · env `PTT_FLASK_CRM_PROPOSALS_RETIRED=1` · `PTT_FLASK_CRM_PAYROLL_RETIRED=1` · `WAVE4P_EXPECT_OPS_WEB=1`

```bash
./scripts/wave4_plus_gate.sh
# hoặc
./scripts/crm_flask_migration_pack.sh wave4-plus
```

**Còn Flask sau Wave 4+:** payroll full `/crm/payroll`, proposals matrix UI, RE/finance (Wave 5–7).

---

## Wave 4 (legacy table)

| Module | Pages |
|--------|-------|
| Sales | `/crm/sales` |
| KPI | `/crm/kpi`, `/crm/staff-kpi` |
| Staff workspace | `/crm/staff` |

---

## Wave 5 — RE projects + Payroll (Tháng 5–7, có thể readonly lâu hơn)

| Module | Nest | ops-web | Flask retire |
|--------|------|---------|--------------|
| RE projects | `re-projects/` MVP ✅ | `/crm/re-projects` ✅ | readonly |
| Payroll extended | `payroll/` policy+attendance+compute ✅ | `/crm/payroll` ✅ | readonly |

**DoD Wave 5:** `./scripts/wave5_gate.sh` PASS · env `PTT_FLASK_CRM_RE_PROJECTS_RETIRED=1` · `PTT_FLASK_CRM_PAYROLL_RETIRED=1` · `WAVE5_EXPECT_OPS_WEB=1`

```bash
./scripts/wave5_gate.sh
# hoặc
./scripts/crm_flask_migration_pack.sh wave5
```

**Còn Flask sau Wave 5:** RE KPI/staff phased, finance (Wave 6–7).

---

## Wave 5+ — RE accounting phase

| Module | Nest | ops-web | Flask retire |
|--------|------|---------|--------------|
| RE accounting | `re-projects/` dashboard+cash-flow ✅ | `/crm/re-projects/[id]` accounting tab ✅ | readonly |

**DoD Wave 5+:** `./scripts/wave5_plus_gate.sh` PASS · env `PTT_FLASK_CRM_RE_PROJECTS_ACCOUNTING_RETIRED=1` · `WAVE5P_EXPECT_ACCOUNTING_NEST=1`

```bash
./scripts/wave5_plus_gate.sh
# hoặc
./scripts/crm_flask_migration_pack.sh wave5-plus
```

**Còn Flask sau Wave 5+:** RE KPI/staff, finance (Wave 6–7).

---

## Wave 5++ — RE KPI/risks/budget phase

| Module | Nest | ops-web | Flask retire |
|--------|------|---------|--------------|
| RE KPI | `re-projects/` `:id/kpis` ✅ | `/crm/re-projects/[id]` KPI tab ✅ | readonly |
| RE budget | `re-projects/` `:id/budget` ✅ | `/crm/re-projects/[id]` Budget tab ✅ | readonly |
| RE risks | `re-projects/` `:id/risks` ✅ | `/crm/re-projects/[id]` Risks tab ✅ | readonly |

**DoD Wave 5++:** `./scripts/wave5_pp_gate.sh` PASS · env `PTT_FLASK_CRM_RE_PROJECTS_KPI_RISKS_RETIRED=1` · `WAVE5PP_EXPECT_KPI_RISKS_NEST=1`

```bash
./scripts/wave5_pp_gate.sh
# hoặc
./scripts/crm_flask_migration_pack.sh wave5-pp
```

**Còn Flask sau Wave 5++:** staff/lead-config, finance (Wave 6–7).

---

## Wave 5+++ — RE staff/lead-config/workflow/export phase

| Module | Nest | ops-web | Flask retire |
|--------|------|---------|--------------|
| RE staff pool | `re-projects/` `:id/staff` ✅ | `/crm/re-projects/[id]` Staff tab ✅ | readonly |
| RE lead config | `re-projects/` `:id/lead-config` ✅ | `/crm/re-projects/[id]` Lead config tab ✅ | readonly (webhook ingest edge) |
| RE workflow | `re-projects/` `:id/workflow` ✅ | `/crm/re-projects/[id]` Workflow tab ✅ | readonly |
| RE export | `re-projects/` `:id/export` ✅ | `/crm/re-projects/[id]` Export tab ✅ | readonly |

**DoD Wave 5+++:** `./scripts/wave5_ppp_gate.sh` PASS · env `PTT_FLASK_CRM_RE_PROJECTS_OPS_RETIRED=1` · `WAVE5PPP_EXPECT_OPS_NEST=1`

```bash
./scripts/wave5_ppp_gate.sh
# hoặc
./scripts/crm_flask_migration_pack.sh wave5-ppp
```

**Còn Flask sau Wave 5+++:** finance (Wave 6–7).

---

## Wave 6 — Finance / owner-weekly phase

| Module | Nest | ops-web | Flask retire |
|--------|------|---------|--------------|
| Business dashboard | `finance/` `business-dashboard` ✅ | `/crm/business-dashboard` ✅ | readonly |
| Financials | `finance/` `financials` + `kpi-alerts` ✅ | `/crm/financials` ✅ | readonly |
| Owner weekly | `owner-weekly/` `cash-snapshots` + `export` ✅ | `/crm/owner-weekly` ✅ | readonly |

**DoD Wave 6:** `./scripts/wave6_gate.sh` PASS · env `PTT_FLASK_CRM_FINANCE_RETIRED=1` · `WAVE6_EXPECT_FINANCE_NEST=1`

```bash
./scripts/wave6_gate.sh
# hoặc
./scripts/crm_flask_migration_pack.sh wave6
```

**Còn Flask sau Wave 6:** svc-finance lifecycle payments (Wave 7), crm_shell global retire.

---

## Wave 7 — Phase 5 readiness (crm_shell + svc-finance)

| Module | Nest | ops-web | Flask retire |
|--------|------|---------|--------------|
| CRM board hub | `crm-board/` `/api/crm/board` ✅ | `/crm` ✅ | redirect |
| Svc-finance | `svc-finance/` summary + svc-payments ✅ | service-delivery detail | readonly |

**DoD Wave 7:** `./scripts/wave7_gate.sh` PASS · env `PTT_FLASK_CRM_SHELL_RETIRED=1` · `WAVE7_EXPECT_SHELL_OPS_WEB=1` · gap `can_stop_ptt_service=true`

```bash
./scripts/wave7_gate.sh
# hoặc
./scripts/crm_flask_migration_pack.sh wave7
```

**Sau Wave 7:** registry `partial=0`, `flask_only=0` → eligible for Phase 5 dry-run.

---

## Wave 5 (legacy table)

| Module | Ghi chú |
|--------|---------|
| RE projects | ~60 API — chia phase: inventory → accounting → KPI |
| Payroll / attendance | ít frequency — có thể giữ Flask readonly thêm 4 tuần |

---

## Wave 7 — Global Flask stop (Phase 5)

**Chỉ khi:** `./scripts/crm_flask_migration_pack.sh gap` → `can_stop_ptt_service: true`

```bash
set -a && source deploy/env.phase5-flask-retire.example && set +a
export CRM_FLASK_REQUIRE_FULL_MIGRATION=1

# Preflight
./scripts/crm_flask_migration_pack.sh phase5-dry   # must PASS
./scripts/staging_phase5_gate_pack.sh

# Prod
sudo -E APPLY=1 ./scripts/close_flask_retirement.sh
```

→ `PTT_FLASK_MONOLITH_MODE=retired` · `systemctl stop ptt.service` · `nginx-rs-flask-retired.conf`

Chi tiết: [`phase5-flask-retirement-checklist.md`](./phase5-flask-retirement-checklist.md)

---

## Ma trận module (registry)

Cập nhật trong `ptt_crm/crm_flask_retirement_registry.py` khi hoàn thành từng module (`FLASK_ONLY` → `PARTIAL` → `RETIRED`).

| Wave | Module IDs |
|------|------------|
| 0 | agency, meta, seo, email, webhooks |
| 1 | leads, hub, **catalog** |
| 2 | customers, intake, cases |
| 3 | marketing_plans, service_lifecycle, sop |
| 4 | sales, kpi, staff, proposals |
| 5 | re_projects, payroll |
| 6 | finance |
| 7 | crm_shell → global retire |

---

## Rollback

| Sự cố | Hành động |
|-------|-----------|
| ops-web thiếu feature | `PTT_FLASK_MONOLITH_MODE=readonly`; nginx tạm proxy Flask |
| Nest outage | `PTT_WEBHOOKS_FLASK_FALLBACK=1` (tạm); restore nginx backup |
| Stop Flask quá sớm | `systemctl enable --now ptt.service`; restore `.pre-phase5.bak` nginx |

---

## KPI Definition of Done (toàn CRM)

- [ ] `crm_flask_retirement_registry`: 0 `flask_only`
- [ ] 0 route Flask mutating prod
- [ ] 0 Nest proxy `PTT_FLASK_MONOLITH_URL`
- [ ] Staff >95% traffic ops.pttads.vn
- [ ] `ptt.service` stopped ≥14 ngày soak
- [ ] Human sign-off Phase 5

---

## Lệnh tham chiếu

```bash
cp deploy/env.crm-flask-migration.example .env.crm
set -a && source .env.crm && set +a

./scripts/crm_flask_migration_pack.sh gap
./scripts/crm_flask_migration_pack.sh wave0
./scripts/crm_flask_migration_pack.sh gates
```

Artifacts: `.local-dev/crm-flask-retirement-gate-report.json`
