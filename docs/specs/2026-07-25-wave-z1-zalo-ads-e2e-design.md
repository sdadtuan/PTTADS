# Wave Z1 — Zalo Ads CPL E2E (Track Z)

**Date:** 2026-07-25  
**Status:** PO approved  
**Signed off:** 2026-07-25  
**Depends on:** Z0 (channel account, hub map, webhook), Agency PG, worker infra  
**Spec:** [`SPEC_ZALO_ADS_OPERATING_SYSTEM.md`](../SPEC_ZALO_ADS_OPERATING_SYSTEM.md)  
**Backlog:** [`2026-07-25-zalo-ads-implementation-backlog.md`](2026-07-25-zalo-ads-implementation-backlog.md)

## PO decisions

| Topic | Decision |
|-------|----------|
| Scope | **Z1_full** — Staff hub + Portal + OAuth pilot + manual sync |
| Hub UX | **Separate page** — `/zalo/zalo-ads` (+ combined nav deferred **Z2**) |
| OAuth | **oauth_pilot** — Nest OAuth + pilot/stub banner (mirror Google B6-S6) |
| Sync | **manual_button** — enqueue `zalo_insights_sync` job |
| Lead | **webhook_primary** — form poll deferred to **Z2** |
| Cap | **crm_zalo_ads** view + export |
| Execute | **go** |

## PO sign-off

| Role | Decision | Date |
|------|----------|------|
| PO | **Approved** — triển khai Wave Z1 theo backlog Sprint S1–S2 | 2026-07-25 |
| Engineering | Ready — pattern Google B6-S6; Z0 foundation verified | 2026-07-25 |

**In scope for implementation (S1–S2):**

- DDL `zalo_insights_sync_state` + worker `zalo_insights_sync`
- Nest hub API + OAuth pilot + sync endpoints + cap `crm_zalo_ads`
- ops-web `/zalo/zalo-ads` + agency Connect/Sync Zalo + OpsNav
- portal-web `/zalo` + PerformanceChannel `zalo`
- E2E `zalo-ads.spec.ts` + ops guide draft

**Explicitly deferred:**

- Form poll + `/zalo/leads` → **Wave Z2**
- Combined nav `/meta/ads-combined` Zalo tab → **Wave Z3**
- Campaign API write → **Wave Z4**

**Pre-requisites before prod cutover:**

- [ ] Zalo Developer App created; OAuth redirect URI registered
- [ ] Env `PTT_ZALO_*` set on staging
- [ ] Pilot client list `PTT_ZALO_ADS_PILOT_CLIENTS` agreed with AM

## Flow

```
AM add channel=zalo → Connect Zalo OAuth → token vault
    → hub map channel=zalo
    → Sync Zalo now → job zalo_insights_sync → daily_performance
    → Staff /zalo/zalo-ads CPL hub + Portal /zalo
    → Webhook lead (existing) → CRM → CPL closed-loop
```

## API (staff)

| Method | Path | Cap |
|--------|------|-----|
| GET | `/api/v1/zalo-ads/hub` | crm_zalo_ads view |
| GET | `/api/v1/zalo-ads/hub/export` | crm_zalo_ads export |
| GET | `/api/v1/zalo-ads/oauth/start` | crm_agency write |
| GET | `/api/v1/zalo-ads/oauth/callback` | public (Zalo redirect) |
| GET | `/api/v1/zalo-ads/pilot-status` | view |
| POST | `/api/v1/clients/:id/sync/zalo-insights` | crm_agency write |
| GET | `/api/v1/clients/:id/zalo/sync-status` | view |

## UI

- ops-web: `/zalo/zalo-ads`, agency Channels OAuth + Sync Zalo, OpsNav section Zalo
- portal-web: `/zalo` (mirror `/google`)
- Extend `PerformanceChannel` type: `'meta' | 'google' | 'zalo'`

## Worker

- New package: `ptt_zalo/insights_sync.py`
- Handler: `ptt_jobs/handlers/zalo_insights_sync.py`
- DDL: `docs/specs/2026-07-25-postgresql-ddl-zalo-insights-sync-state.sql`

## Env

- `PTT_ZALO_APP_ID`, `PTT_ZALO_APP_SECRET`, `PTT_ZALO_OAUTH_REDIRECT_URI`
- `CRM_ZALO_WEBHOOK_SECRET`
- `PTT_ZALO_INSIGHTS_SYNC`, `PTT_ZALO_ADS_STUB`, `PTT_ZALO_ADS_PILOT`, `PTT_ZALO_ADS_PILOT_CLIENTS`

## Acceptance (Wave Z1)

- [ ] Hub CPL matches manual calculation ± rounding
- [ ] Portal client A cannot see client B Zalo metrics
- [ ] Sync job idempotent per client+date
- [ ] E2E `zalo-ads.spec.ts` green in CI
