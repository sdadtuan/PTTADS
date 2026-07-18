# Phase 2 UAT — Critical path & sign-off

> **Mục tiêu:** UAT critical path + sign-off AM/Admin trước khi ký Phase 2 Done và bắt đầu Phase 3 planning.

## Automated gate (repo)

```bash
# Subset tự động
./scripts/phase2_uat_gate.py --am-name "Nguyen A" --admin-name "Admin B"
# Report: .local-dev/phase2-uat-signoff.json

# Full staging pack (khuyến nghị)
set -a && source deploy/env.staging-phase2-gates.example && set +a
./scripts/staging_phase2_gate_pack.sh
# Report: .local-dev/phase2-ops-gate-report.json
```

## Critical path — Track W (Write)

| ID | Test | Cách verify | Pass |
|----|------|-------------|------|
| W-UAT-01 | Nest health write enabled | `curl /health` → `leads_write_enabled: true` | [ ] |
| W-UAT-02 | POST/PATCH staging lead | `./scripts/local_leads_write_staging.sh` | [ ] |
| W-UAT-03 | Assign UI → PG | Agency Ops assign 1 lead; PG `owner_id` đúng | [ ] |
| W-UAT-04 | Shadow lag ≤ 1 phút | `./scripts/sync_lead_shadow.sh` + shadow_state | [ ] |
| W-UAT-05 | Dual-run 0 mismatch | `./scripts/dual_run_write_check.py --sample 50` | [ ] |
| W-UAT-06 | LeadAssigned ≤ 30s | `./scripts/lead_assigned_rmq_e2e.sh` | [ ] |
| W-UAT-07 | 48h soak evidence | `./scripts/write_cutover_prod_gates.sh` | [ ] |
| W-UAT-08 | Rollback drill ≤ 5 min | `.local-dev/rollback-drill-evidence.json` | [ ] |
| W-UAT-09 | OpenAPI freeze CI | `./scripts/ci_openapi_write_freeze.sh` | [ ] |
| W-UAT-10 | W5 defer documented | Prod create deferred Phase 2.1 — PATCH only | [ ] |

## Critical path — Track M (Closed-loop)

| ID | Test | Cách verify | Pass |
|----|------|-------------|------|
| M-UAT-01 | ≥3 client pilot | `PTT_CLOSED_LOOP_CLIENT_CODES` gate pack | [ ] |
| M-UAT-02 | Token + pixel | Agency tab Kênh ads | [ ] |
| M-UAT-03 | Hub map sync | `./scripts/sync_hub_campaign_map.sh` | [ ] |
| M-UAT-04 | Insights T-1 | `daily_performance` rows | [ ] |
| M-UAT-05 | CPL tab data | Agency Campaign CPL tab | [ ] |
| M-UAT-06 | ROAS stub column | UI shows stub when conversion_value=0 | [ ] |
| M-UAT-07 | Meta sync alert | Force fail → inbox alert | [ ] |
| M-UAT-08 | CAPI Lead pilot | `capi_event_log` sent/skipped (≥1 client) | [ ] |

## Cross-cutting

| ID | Test | Pass |
|----|------|------|
| X-UAT-01 | Regression L01–L26 (critical subset) | [ ] |
| X-UAT-02 | Sentry dashboards | [sentry-phase2-dashboards.md](./sentry-phase2-dashboards.md) | [ ] |
| X-UAT-03 | Meta runbooks acknowledged | token refresh + insights replay | [ ] |
| X-UAT-04 | Backup ptt.db + pg_dump policy | [ ] |
| X-UAT-05 | Prod cutover dry-run | `./scripts/prod_write_cutover.sh` | [ ] |

## Sign-off

### Account Manager

- [ ] CPL dashboard reviewed for pilot clients (≥3)
- [ ] Assign flow OK on Agency Ops UI
- [ ] Closed-loop data T-1 acceptable for AM reporting

**Name:** __________________ **Date:** __________ **Signature:** __________

### Admin / DevOps

- [ ] Write cutover runbook §4–§8 reviewed
- [ ] 48h soak evidence attached (real timer preferred)
- [ ] Rollback drill evidence ≤ 5 min
- [ ] Systemd timers enabled (shadow, meta-insights, token-refresh, write-soak)
- [ ] Sentry Phase 2 dashboards live

**Name:** __________________ **Date:** __________ **Signature:** __________

## W5 decision (Phase 2.1)

**Prod `POST /api/v1/leads`** — deferred. Phase 2 prod cutover = **PATCH assign/status only**; staging create uses id ≥ 900_000_000.

## Artifacts to attach

| File | Description |
|------|-------------|
| `.local-dev/phase2-ops-gate-report.json` | Full staging gate pack |
| `.local-dev/write-cutover-prod-gates.json` | OpenAPI + soak + gates |
| `.local-dev/rollback-drill-evidence.json` | Rollback ≤ 5 min |
| `.local-dev/lead-assigned-rmq-e2e.json` | LeadAssigned E2E |
| `.local-dev/prod-write-cutover-report.json` | Prod cutover dry-run/apply |
| `.local-dev/phase2-uat-signoff.json` | Sign-off template export |

---

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-17 | Phase 2 UAT + sign-off checklist |
