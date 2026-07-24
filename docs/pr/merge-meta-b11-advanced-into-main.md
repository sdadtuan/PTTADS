# Pull Request: Merge Meta Enterprise B11 Advanced into `main`

Use this document when opening the PR on GitHub.

| Field | Value |
|-------|-------|
| **Title** | feat(meta-b11): Advanced intelligence — z-score, forecast, multi-pixel |
| **Base** | `main` |
| **Compare** | `feat/meta-b11-advanced` |
| **Remote** | https://github.com/sdadtuan/PTTADS |
| **Create PR** | https://github.com/sdadtuan/PTTADS/compare/main...feat/meta-b11-advanced?expand=1 |

---

## Summary

- **B11 Advanced** — z-score stat anomalies, CPL/spend forecast, multi-pixel CRUD + CAPI primary routing, intelligence snapshot gzip export, DDL v7, ops-web panels, wave B11 gates.
- **Stack note:** Branch includes **B10 Intelligence** commits (not yet on `main`). Review as combined stack or merge B10 first then retarget.

**Scope:** 4 commits ahead of `main` (3× B10 + 1× B11).

### Commits included

- `f3bc893` — feat(meta-b10): add Intelligence layer with ROAS, anomalies, and budget recommendations
- `9e7ec84` — feat(meta-b10): add adset insights API, ROAS chart, and Playwright E2E
- `966e60d` — docs(pr): add B10 Intelligence merge checklist for main
- `57536d1` — feat(meta-b11): add Advanced intelligence with z-score, forecast, and multi-pixel

---

## API (Nest) — B11

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/meta/anomalies?mode=stat` | z-score: `spend_zscore`, `cpl_zscore` (14d window) |
| GET | `/api/v1/meta/forecast` | CPL/spend linear slope + 7d projection |
| GET/POST/PATCH | `/api/v1/meta/pixels` | Multi-pixel registry |
| POST | `/api/v1/meta/intelligence/snapshot` | Manual gzip export + PG metadata |

---

## ops-web — B11

- Route: `/meta/intelligence` (extended)
- New sections: **Stat anomalies (z-score)**, **Forecast (CPL)**, **Multi-pixel**
- Flags: `NEXT_PUBLIC_PTT_META_ANOMALY_STAT_ENABLED`, `NEXT_PUBLIC_PTT_META_FORECAST_ENABLED`, `NEXT_PUBLIC_PTT_META_PIXELS_ENABLED`

---

## Pre-merge checklist (reviewer)

- [ ] DDL order: **v4 → v5 → v6 → v7** (`./scripts/apply_pg_ddl_v7_meta_advanced.sh`)
- [ ] B11 flags default **off** (`deploy/env.meta-enterprise-b11.example`)
- [ ] `./scripts/wave_b11_gate.sh` PASS (includes B10 regression)
- [ ] CAPI primary pixel routing verified when `PTT_META_PIXELS_ENABLED=1`
- [ ] Owner-weekly digest includes snapshot block when `PTT_META_INTEL_SNAPSHOT_ENABLED=1`

---

## Test plan

- [ ] `./scripts/wave_b11_gate.sh`
- [ ] `./scripts/wave_b10_gate.sh` (regression)
- [ ] Nest: `npm test -- --testPathPattern=meta-intelligence`
- [ ] ops-web build + `/meta/intelligence` smoke
- [ ] Staging: apply DDL v7, enable B11 flags, smoke stat/forecast/pixels/snapshot endpoints

---

## PR body (paste into GitHub)

```markdown
## Summary
- B11 Advanced: z-score anomalies, forecast API, multi-pixel + CAPI routing, intelligence snapshot, DDL v7, ops-web UI, wave_b11 gates.
- Branch stacks on B10 Intelligence (3 commits) — review combined or merge B10 first.

## Test plan
- [ ] `./scripts/wave_b11_gate.sh`
- [ ] Apply DDL v7 on staging PG
- [ ] Enable flags from `deploy/env.meta-enterprise-b11.example`
- [ ] Smoke `/meta/intelligence` B11 sections
- [ ] Verify primary pixel routes CAPI
```
