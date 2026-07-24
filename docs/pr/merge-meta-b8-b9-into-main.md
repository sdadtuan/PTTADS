# Pull Request: Merge Meta Enterprise B8 + B9 into `main`

Use this document when opening the PR on GitHub.

| Field | Value |
|-------|-------|
| **Title** | feat(meta): Meta Enterprise B8 hub/alerts + B9 conversion tracking pipeline |
| **Base** | `main` |
| **Compare** | `feat/meta-b9-sprint-f-conversion-pipeline` |
| **Remote** | https://github.com/sdadtuan/PTTADS |
| **Create PR** | https://github.com/sdadtuan/PTTADS/compare/main...feat/meta-b9-sprint-f-conversion-pipeline?expand=1 |

---

## Summary

- **B9 Sprint E** — PostgreSQL DDL v5 (conversion rules, CAPI log extensions), Nest `meta-tracking` API skeleton, contract tests.
- **B8** — Meta Ads hub tabs (clients/campaigns/alerts), PG `meta_alerts`, sync status, hub map suggest, portal attribution footer, wave B8 gates/E2E.
- **B9 Sprint F–H** — Conversion sync/eval/archive jobs, CAPI dispatch extensions, `/meta/tracking` ops-web UI, Launch QA Meta auto-checklist bridge, wave B9 gates/smoke/Playwright, 30d pilot soak runbook.

**Scope:** ~153 files, +15,955 / −538 lines (4 commits ahead of `main`).

### Commits included

- `55019e0` — feat(meta-b9-sprint-e): Conversion DDL v5 and tracking API skeleton
- `fb76a70` — feat(meta-b8): Meta enterprise hub, alerts, and portal attribution
- `78aaa82` — merge(meta-b8): hub alerts and portal attribution into sprint-f
- `ec1b1bd` — feat(meta-b9-sprint-fgh): conversion pipeline, tracking UI, and QA gates

---

## Why merge now

Production VPS is on `main` at `b46b46e` (Wave B7 only). Meta Enterprise work lives on the feature branch and is required before enabling closed-loop CAPI, tracking health UI, and Launch QA Meta gates.

---

## Pre-merge checklist (reviewer)

- [ ] DDL migration order documented and tested: **v4 (B8) → v5 (B9)**
- [ ] Feature flags default **off** in production (`PTT_META_ALERTS_ENABLED`, `PTT_META_TRACKING_ENABLED`, `PTT_CAPI_ENABLED`)
- [ ] No secrets in env examples
- [ ] Worker job handlers registered for new job types
- [ ] ops-web build passes with new `/meta/tracking` route

---

## Deploy plan (post-merge to VPS)

### 1. Pull code

```bash
cd /var/www/ptt
git pull origin main
```

### 2. Apply PostgreSQL DDL (in order)

```bash
./scripts/apply_pg_ddl_v4_meta_enterprise.sh   # B8: meta_alerts, hub extensions
./scripts/apply_pg_ddl_v5_meta_conversion.sh   # B9: conversion_rules, capi log cols
```

### 3. Environment (start with flags off)

Copy and merge from:

- `deploy/env.meta-enterprise-b8.example`
- `deploy/env.meta-enterprise-b9.example`

Minimum production-safe defaults:

```bash
PTT_META_ALERTS_ENABLED=0
NEXT_PUBLIC_PTT_META_ALERTS_ENABLED=0
PTT_META_TRACKING_ENABLED=0
NEXT_PUBLIC_PTT_META_TRACKING_ENABLED=0
PTT_CAPI_ENABLED=0
PTT_META_CONVERSION_SYNC_ENABLED=0
PTT_META_INSIGHTS_ARCHIVE_ENABLED=0
PTT_LAUNCH_QA_META_STRICT=0
```

Enable per pilot client after smoke gates pass.

### 4. Rebuild & restart

```bash
# API + ops-web (adjust to your compose/systemd names)
docker compose build ptt-crm-api ops-web
docker compose up -d ptt-crm-api ops-web ptt-worker
```

### 5. Smoke gates

```bash
WAVE_B8_SKIP_E2E=1 ./scripts/wave_b8_gate.sh
WAVE_B9_SKIP_BUILD=1 WAVE_B9_SKIP_NEST=1 WAVE_B9_SKIP_E2E=1 ./scripts/wave_b9_gate.sh
```

Full E2E when staging stack is up:

```bash
./scripts/wave_b8_smoke.sh
./scripts/wave_b9_smoke.sh
```

---

## Test plan

### Automated

- [ ] `python3 -m unittest tests.test_meta_alerts tests.test_b8_portal_qa`
- [ ] `python3 -m unittest tests.test_b9_ddl tests.test_b9_tracking_qa tests.test_conversion_sync tests.test_tracking_health`
- [ ] `cd services/ptt-crm-api && npm test -- --testPathPattern='meta-tracking|facebook-hub-b8'`
- [ ] `cd services/ops-web && npm run build`
- [ ] `./scripts/wave_b8_gate.sh` (with PG + optional E2E)
- [ ] `./scripts/wave_b9_gate.sh`

### Manual (ops-web)

- [ ] `/meta/facebook-ads` — tabs Clients / Campaigns / Alerts, sync chip, export CSV
- [ ] `/meta/facebook-ads` — CAPI badge column when `NEXT_PUBLIC_PTT_META_TRACKING_ENABLED=1`
- [ ] `/meta/tracking` — KPI grid, account table, conversion rules, CAPI events, preflight checklist
- [ ] Launch QA panel — auto items: `meta_pixel_configured`, `meta_capi_test_ok`, `meta_hub_map_coverage`, `meta_capi_recent_sent`

### Manual (portal-web)

- [ ] Performance panel shows attribution model, unmapped spend %, data freshness footer

### Rollback

- Revert merge commit on `main` and redeploy previous image/tag
- DDL v4/v5 are additive; rollback code only (do not drop tables in prod without runbook)

---

## Risk notes

| Area | Risk | Mitigation |
|------|------|------------|
| DDL v4/v5 | Schema drift on prod PG | Apply scripts in order; verify with gate scripts |
| CAPI dispatch | Accidental live events | `PTT_CAPI_ENABLED=0`, pilot client list |
| Launch QA strict | Blocks launch_ready | Keep `PTT_LAUNCH_QA_META_STRICT=0` until pilot OK |
| Worker load | New scheduled jobs | Enable jobs incrementally via env flags |

---

## Related docs

- `docs/SPEC_META_ENTERPRISE_PTTADS.md`
- `docs/specs/2026-07-24-meta-enterprise-phase0-b8-implementation-plan.md`
- `docs/specs/2026-07-24-meta-enterprise-b9-tracking-implementation-plan.md`
- `docs/specs/2026-07-24-meta-enterprise-ui-ux-architecture-design.md`
- `docs/runbooks/b9-tracking-pilot-soak.md`

---

## GitHub PR body (copy-paste)

```markdown
## Summary

- Land Meta Enterprise **B8** (hub tabs, PG alerts, portal attribution) and **B9 E/F/G/H** (conversion DDL, tracking API, CAPI jobs, `/meta/tracking` UI, Launch QA Meta bridge, QA gates).
- 4 commits, ~153 files. All new production features default **off** via env flags.

## Test plan

- [ ] Apply DDL v4 then v5 on staging PG
- [ ] `wave_b8_gate.sh` + `wave_b9_gate.sh` pass
- [ ] ops-web: `/meta/facebook-ads`, `/meta/tracking`
- [ ] Nest: meta-tracking + facebook-hub-b8 e2e specs
- [ ] Portal: attribution footer on performance views
- [ ] Deploy VPS with flags off; enable pilot after smoke

See `docs/pr/merge-meta-b8-b9-into-main.md` for full deploy runbook.
```
