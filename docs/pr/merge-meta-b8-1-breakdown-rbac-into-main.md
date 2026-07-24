# Pull Request: Merge Meta Enterprise B8.1 Breakdown + RBAC into `main`

Use this document when opening the PR on GitHub.

| Field | Value |
|-------|-------|
| **Title** | feat(meta-b8-1): publisher_platform breakdown and granular Meta RBAC |
| **Base** | `main` |
| **Compare** | `feat/meta-b8-1-breakdown-rbac` |
| **Remote** | https://github.com/sdadtuan/PTTADS |
| **Create PR** | https://github.com/sdadtuan/PTTADS/compare/main...feat/meta-b8-1-breakdown-rbac?expand=1 |

---

## Summary

- **Breakdown (B8.1)** — PostgreSQL DDL v8 `daily_performance_breakdown`, Graph sync with `publisher_platform` dimension, Nest `GET /meta/insights/breakdown`, ops-web expandable campaign breakdown panel.
- **Granular RBAC (B8.1)** — Buyer can submit campaign writes but not approve; Tracking can configure rules (`crm_agency.configure`) but not approve writes; AM/Admin retains approve. Tracking configure guard no longer falls back to `crm_facebook_ads.view`.
- **Gates** — `wave_b81_gates.py`, `./scripts/wave_b8_1_gate.sh`, seed script `seed_staff_meta_rbac_b81.py`.

**Scope:** 31 files, +1,514 / −42 lines (3 commits ahead of `main`).

### Commits included

- `fa26f43` — feat(meta-b8-1): publisher_platform breakdown and granular Meta RBAC
- `af42a53` — docs(pr): add B8.1 breakdown + RBAC merge checklist for main
- `ded02f3` — docs(pr): fix B8.1 merge checklist commit hash

---

## API (Nest)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/meta/insights/breakdown` | Query: `client_id`, `campaign_id`, `type=publisher_platform`, `from`, `to`, `days` |

Feature flag: `PTT_META_INSIGHTS_BREAKDOWN=0` (default off). Returns `disabled: true` when flag off or DDL v8 not applied.

---

## ops-web

- **Facebook Ads hub** — expandable campaign row → `MetaBreakdownPanel` (publisher platform spend table)
- Flag: `NEXT_PUBLIC_PTT_META_INSIGHTS_BREAKDOWN=0` (default off)
- Caps helpers: `canConfigureMetaTracking`, `canApproveMetaCampaignWrite`, `canSubmitMetaCampaignWrite`

---

## RBAC matrix

| Staff role | Caps | Campaign write submit | Campaign write approve | Tracking configure |
|------------|------|----------------------|------------------------|-------------------|
| Buyer (MKT-02) | `crm_facebook_ads.view` | Yes | No | No |
| Tracking (TECH-01) | `crm_agency.configure` | No | No | Yes |
| AM/Admin (MKT-01) | `crm_facebook_ads.approve` | Yes | Yes | Yes |

Seed: `python3 scripts/seed_staff_meta_rbac_b81.py`

---

## Pre-merge checklist (reviewer)

- [ ] DDL order: **v4 (B8) → v5 (B9) → v6 (B10) → v8 (B8.1 breakdown)**
- [ ] Feature flag default **off** (`PTT_META_INSIGHTS_BREAKDOWN=0`)
- [ ] `./scripts/wave_b8_1_gate.sh` PASS (B81-G01..G05)
- [ ] B8 regression still passes via B81-G04
- [ ] Tracking guard change reviewed — configure requires `crm_agency.configure` only
- [ ] No secrets in `deploy/env.meta-enterprise-b8-1.example`

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
./scripts/apply_pg_ddl_v6_meta_insights_level.sh
./scripts/apply_pg_ddl_v8_meta_insights_breakdown.sh   # B8.1
```

### 3. Seed RBAC (staging/pilot)

```bash
python3 scripts/seed_staff_meta_rbac_b81.py
```

### 4. Environment (pilot — flag off first)

Copy `deploy/env.meta-enterprise-b8-1.example` into `.env`, then enable after DDL + smoke:

```bash
PTT_META_INSIGHTS_BREAKDOWN=0
NEXT_PUBLIC_PTT_META_INSIGHTS_BREAKDOWN=0
```

Enable per pilot client:

```bash
PTT_META_INSIGHTS_BREAKDOWN=1
NEXT_PUBLIC_PTT_META_INSIGHTS_BREAKDOWN=1
```

### 5. Build & restart

```bash
cd services/ptt-crm-api && npm run build
cd ../ops-web && npm run build
# restart systemd units per runbook
```

### 6. Smoke

```bash
./scripts/wave_b8_1_gate.sh
./scripts/wave_b8_1_smoke.sh          # Nest running + flag=1 + DDL v8
```

---

## Test plan

- [ ] `./scripts/wave_b8_1_gate.sh` — B81-G01..G05 PASS
- [ ] `python3 -m unittest tests.test_insights_breakdown tests.test_meta_rbac_b81 tests.test_b81_breakdown_qa -v`
- [ ] `cd services/ptt-crm-api && npm test -- --testPathPattern='meta-rbac|meta-intelligence'`
- [ ] `cd services/ops-web && npm run build` — `/meta/facebook-ads` includes breakdown panel wiring
- [ ] Manual UI: expand campaign row on Facebook Ads hub with flag on — publisher platform table loads
- [ ] RBAC: Buyer cannot approve write; Tracking can configure rules; AM can approve
- [ ] Regression: `./scripts/wave_b8_gate.sh` (or via B81-G04)

---

## Rollback

Set flags off (no DDL rollback required):

```bash
PTT_META_INSIGHTS_BREAKDOWN=0
NEXT_PUBLIC_PTT_META_INSIGHTS_BREAKDOWN=0
```

Existing `daily_performance` and breakdown rows are preserved.
