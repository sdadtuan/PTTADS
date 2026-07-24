# Pull Request: Merge Meta Enterprise B10 Intelligence into `main`

Use this document when opening the PR on GitHub.

| Field | Value |
|-------|-------|
| **Title** | feat(meta-b10): Meta Intelligence — ROAS, anomalies, budget recommendations |
| **Base** | `main` |
| **Compare** | `feat/meta-b10-intelligence` |
| **Remote** | https://github.com/sdadtuan/PTTADS |
| **Create PR** | https://github.com/sdadtuan/PTTADS/compare/main...feat/meta-b10-intelligence?expand=1 |

---

## Summary

- **B10 core** — Python anomaly/ROAS/budget-recommend engines, Nest `meta-intelligence` API, ops-web `/meta/intelligence` UI, `meta_alerts_eval` B10 hooks, wave B10 gates/smoke.
- **B10 extend** — `GET /meta/insights/daily?level=adset`, DDL v6 `insight_level` columns, ROAS daily bar chart, Playwright E2E for `/meta/intelligence`.

**Scope:** 45 files, +3,777 lines (2 commits ahead of `main`).

### Commits included

- `f3bc893` — feat(meta-b10): add Intelligence layer with ROAS, anomalies, and budget recommendations
- `9e7ec84` — feat(meta-b10): add adset insights API, ROAS chart, and Playwright E2E

---

## API (Nest)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/meta/anomalies` | Median spikes: `spend_spike`, `cpl_spike`, `roas_low` |
| GET | `/api/v1/meta/roas` | ROAS series + summary + attribution |
| GET | `/api/v1/meta/budget-recommendations` | Read-only (`read_only: true`) |
| GET | `/api/v1/meta/insights/daily?level=adset` | Extended facts (requires DDL v6 + flag) |

---

## ops-web

- Route: `/meta/intelligence`
- Sections: ROAS KPI + chart, adset insights table, anomalies, budget recommendations + CTA → campaign-writes
- Nav: **Meta Intelligence** when `NEXT_PUBLIC_PTT_META_*` flags on

---

## Pre-merge checklist (reviewer)

- [ ] DDL order: **v4 (B8) → v5 (B9) → v6 (B10 adset granularity)**
- [ ] Feature flags default **off** (`PTT_META_ANOMALY_ENABLED`, `PTT_META_ROAS_ENABLED`, `PTT_META_INSIGHTS_LEVEL=campaign`)
- [ ] B9 CAPI soak ≥30d recommended before enabling B10 in prod
- [ ] `./scripts/wave_b10_gate.sh` PASS (10/10 with default skips)
- [ ] No secrets in env examples

---

## Deploy plan (post-merge)

### 1. Pull code

```bash
cd /var/www/ptt
git pull origin main
```

### 2. Apply PostgreSQL DDL (in order)

```bash
./scripts/apply_pg_ddl_v4_meta_enterprise.sh
./scripts/apply_pg_ddl_v5_meta_conversion.sh
./scripts/apply_pg_ddl_v6_meta_insights_level.sh   # B10 adset insight_level
```

### 3. Environment (pilot — flags off first)

Copy `deploy/env.meta-enterprise-b10.example` into `.env`, then enable gradually:

```bash
PTT_META_ALERTS_ENABLED=1
PTT_META_ANOMALY_ENABLED=1
PTT_META_ROAS_ENABLED=1
PTT_META_INSIGHTS_LEVEL=adset          # after DDL v6
NEXT_PUBLIC_PTT_META_ANOMALY_ENABLED=1
NEXT_PUBLIC_PTT_META_ROAS_ENABLED=1
```

### 4. Build & restart

```bash
cd services/ptt-crm-api && npm run build
cd ../ops-web && npm run build
# restart systemd units per runbook
```

### 5. Smoke

```bash
./scripts/wave_b10_gate.sh
./scripts/wave_b10_smoke.sh          # Nest running + flags=1
./scripts/playwright_ops_meta_intelligence_e2e.sh   # optional E2E
```

---

## Test plan

- [ ] `./scripts/wave_b10_gate.sh` — B10-G01..G10 PASS
- [ ] `python3 -m unittest tests.test_meta_anomaly tests.test_meta_roas tests.test_meta_budget_recommend tests.test_insights_daily tests.test_b10_intelligence_qa -v`
- [ ] `cd services/ptt-crm-api && npm test -- --testPathPattern=meta-intelligence`
- [ ] `cd services/ops-web && npm run build` — route `/meta/intelligence` present
- [ ] Manual UI: `/meta/intelligence` — ROAS chart, anomalies, recommendations CTA
- [ ] API smoke: `./scripts/wave_b10_smoke.sh` with staging flags
- [ ] Regression: `./scripts/wave_b9_gate.sh` (or B10 gate B9-G08)

---

## Rollback

Set flags off (no DDL rollback required):

```bash
PTT_META_ANOMALY_ENABLED=0
PTT_META_ROAS_ENABLED=0
NEXT_PUBLIC_PTT_META_ANOMALY_ENABLED=0
NEXT_PUBLIC_PTT_META_ROAS_ENABLED=0
```

Existing `meta_alerts` rows and `daily_performance` data are preserved.
