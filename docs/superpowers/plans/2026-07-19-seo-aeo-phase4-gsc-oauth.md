# Phase 4 — GSC OAuth + API sync (PostgreSQL only)

> **Ngày:** 2026-07-19 · **Trạng thái:** Implemented (MVP)

## Scope

- GSC OAuth (`webmasters.readonly`) — tokens in `seo_aeo.seo_client_settings.integrations_json`
- Search Console API sync → `seo_gsc_daily_stats` via `seo_pg_only()` (**không ghi SQLite**)
- Job type `seo_gsc_sync` + worker handler
- UI: Technical Console — Kết nối Google, Sync OAuth

## Env

| Variable | Purpose |
|----------|---------|
| `PTT_GSC_OAUTH_CLIENT_ID` | Google OAuth client (fallback: `PTT_GOOGLE_ADS_CLIENT_ID`) |
| `PTT_GSC_OAUTH_CLIENT_SECRET` | OAuth secret |
| `PTT_GSC_OAUTH_REDIRECT_URI` | Callback — register `/api/v1/seo/gsc/oauth/callback` |
| `PTT_TOKEN_VAULT_KEY` | Encrypt refresh tokens (optional; dev uses `plain:` prefix) |
| `PTT_GSC_SYNC_STUB=1` | Stub API rows for dev/test |
| `PTT_GSC_REFRESH_TOKEN` | Dev pilot refresh token |

## Routes

| Method | Path |
|--------|------|
| GET | `/api/v1/seo/clients/:id/gsc/oauth/url` |
| GET | `/api/v1/seo/gsc/oauth/callback` |
| GET | `/api/v1/seo/clients/:id/gsc/integration` |
| POST | `/api/v1/seo/clients/:id/gsc/sync` |

## Worker

```bash
# Job queued on POST sync; or inline when PTT_JOBS_SYNC_FALLBACK=1
python3 -m ptt_worker
```

## Tests

```bash
python3 -m unittest tests.test_seo_aeo_phase4_gsc -v
```

## Not in Phase 4 MVP

- GA4 OAuth
- Daily cron timer (add systemd timer later)
- Site picker UI (uses first site or `site_url` prompt)
