# Wave B2 — Agency workflows & side effects

> Kích hoạt side effects giống Flask: Temporal nudge, `ClientOnboarded`, job `meta_insights_sync`, token vault, leads tab, KPI CRUD, notification links.

## Tiên quyết

| Env | Mục đích |
|-----|----------|
| `PTT_JOBS_ENABLED=1` | Enqueue `meta_insights_sync` khi activate / connect token / sync manual |
| `PTT_TOKEN_VAULT_KEY` | AES-256-GCM vault cho Meta access token (DDL v3 `channel_account_tokens`) |
| `PTT_CLIENT_STRICT_ONBOARDING=1` | (tuỳ chọn) checklist bắt buộc trước activate |
| `DATABASE_URL` | PG agency tables + `domain_events`, `job_queue` |

Worker job queue phải chạy (systemd hoặc process riêng) để xử lý `meta_insights_sync`.

## Deploy VPS

```bash
cd /var/www/ptt
sudo -u deploy -H bash -lc 'git pull origin main'
chmod +x scripts/wave_b2_deploy.sh scripts/wave_b2_smoke.sh
sudo -u deploy -H bash -lc 'cd /var/www/ptt && export NEXT_PUBLIC_PTT_API_URL=https://rs.pttads.vn && ./scripts/wave_b2_deploy.sh'
# nếu deploy user không restart được systemd:
sudo systemctl restart ptt-crm-api ptt-ops-web
```

## Smoke

```bash
cd /var/www/ptt
set -a && source .env && set +a
ADMIN_PASSWORD="$ADMIN_PASSWORD" CLIENT_ID=660e8400-e29b-41d4-a716-446655440001 ./scripts/wave_b2_smoke.sh
```

Kiểm tra thêm thủ công:

| Bước | URL / API | Kỳ vọng |
|------|-----------|---------|
| Activate client | `POST /api/v1/clients/:id/activate` | `side_effects.domain_event_id`, `jobs_enqueued` |
| Checklist tick | `PATCH .../onboarding/items/:key` | Temporal nudge (log Nest) |
| Connect token | Client detail → tab Kênh ads → form token | `token_status=ok`, sync job queued |
| Sync insights | nút "Sync insights now" | job `meta_insights_sync` trong `/agency/jobs` |
| Leads tab | `?tab=leads` | leads có `agency_client_id` |
| Notifications | `/agency/notifications` | click `link_url` |
| KPI CRUD | `/agency/kpi-definitions` | POST/PATCH/DELETE |

## API mới (Nest)

- `GET /api/v1/clients/:id/leads`
- `GET /api/v1/clients/:id/onboarding/workflow-status`
- `PATCH /api/v1/clients/:id/channel-accounts/:accountId/token`
- `POST /api/v1/clients/:id/sync/insights`
- `POST|PATCH|DELETE /api/v1/kpi-definitions[/:code]`

## Rollback

```bash
git checkout <wave-b1-commit>
./scripts/wave_b1_deploy.sh
sudo systemctl restart ptt-crm-api ptt-ops-web
```
