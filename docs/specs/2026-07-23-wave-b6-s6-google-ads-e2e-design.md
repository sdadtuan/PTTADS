# Wave B6-S6 — Google Ads CPL E2E (Track G)

**Date:** 2026-07-23  
**Status:** PO approved  
**Depends on:** B6-S5, Phase 3 Track G infra

## PO decisions

| Topic | Decision |
|-------|----------|
| Scope | **D_full** — Staff hub + Portal + Nest OAuth + manual sync |
| Hub UX | **Separate pages** — `/meta/facebook-ads` + `/google/google-ads` + combined nav |
| OAuth | **oauth_pilot** — Nest OAuth + pilot/stub banner |
| Sync | **manual_button** — enqueue `google_insights_sync` job |
| Cap | **crm_google_ads** view (export optional) |
| Execute | **go** |

## Flow

```
AM connect Google OAuth → refresh token in channel vault
    → hub map channel=google
    → Sync Google now → job google_insights_sync → daily_performance
    → Staff /google/google-ads CPL hub + Portal /google
```

## API (staff)

| Method | Path | Cap |
|--------|------|-----|
| GET | `/api/v1/google-ads/hub` | crm_google_ads view |
| GET | `/api/v1/google-ads/hub/export` | crm_google_ads export |
| GET | `/api/v1/google-ads/oauth/start` | crm_agency write |
| GET | `/api/v1/google-ads/oauth/callback` | public (Google redirect) |
| GET | `/api/v1/google-ads/pilot-status` | view |
| POST | `/api/v1/clients/:id/sync/google-insights` | crm_agency write |

## UI

- ops-web: `/google/google-ads`, `/meta/ads-combined`, agency Channels OAuth + Sync Google
- portal-web: `/google` (mirror `/meta`)

## Env

- `PTT_GOOGLE_ADS_CLIENT_ID`, `PTT_GOOGLE_ADS_CLIENT_SECRET`, `PTT_GOOGLE_OAUTH_REDIRECT_URI`
- `PTT_GOOGLE_INSIGHTS_SYNC`, `PTT_GOOGLE_ADS_STUB`, `PTT_GOOGLE_ADS_PILOT`, `PTT_GOOGLE_ADS_PILOT_CLIENTS`
