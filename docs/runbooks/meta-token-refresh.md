# Runbook — Meta token refresh (Phase 2 M1)

> **Mục tiêu:** Long-lived Marketing API token hợp lệ trên mọi ad account pilot; alert trước khi hết hạn.

## Khi nào chạy

| Trigger | Hành động |
|---------|-----------|
| `ptt-meta-token-refresh.timer` | Tự động 06:00 ICT hàng ngày |
| Token status `expiring` / `expired` trên Agency Ops | Refresh thủ công hoặc cập nhật token mới |
| Meta insights sync fail `missing_access_token` | Kiểm tra vault + refresh |

## Systemd (VPS)

```bash
sudo cp ptt-meta-token-refresh.service ptt-meta-token-refresh.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ptt-meta-token-refresh.timer
sudo systemctl status ptt-meta-token-refresh.timer
```

## Thủ công — refresh job

```bash
cd /var/www/ptt
set -a && source .env && set +a

export PTT_META_TOKEN_REFRESH=1
# Staging/local without Graph:
# export PTT_META_TOKEN_REFRESH_STUB=1

python3 -c "
from ptt_meta.token_refresh import run_token_refresh_job
import json
print(json.dumps(run_token_refresh_job(), indent=2, default=str))
"
```

Hoặc enqueue worker job:

```bash
python3 -c "
from ptt_jobs.enqueue import enqueue_job
enqueue_job('meta_token_refresh', {}, 'meta_token_refresh:daily')
"
python3 -m ptt_worker --once
```

## Cập nhật token mới (UI)

1. Agency Ops → Client → tab **Kênh ads**
2. Meta Ad Account → nhập **Access token** mới + **Token hết hạn**
3. (Optional) **Meta Pixel ID** cho CAPI closed-loop
4. Lưu — token được mã hóa (`PTT_TOKEN_VAULT_KEY` bắt buộc trên VPS)

CLI seed (staging):

```bash
export CLIENT_CODE=DEMO
export META_AD_ACCOUNT_ID=act_1234567890
export META_ACCESS_TOKEN=EAAx...
export META_PIXEL_ID=123456789012345
export TOKEN_EXPIRES=2026-12-31
./scripts/seed_meta_channel_account.py
```

## Verify

```bash
psql "$DATABASE_URL" -c "
  SELECT c.code, a.external_account_id, a.token_status, a.token_expires_at
  FROM client_channel_accounts a
  JOIN clients c ON c.id = a.client_id
  WHERE a.channel = 'meta'
  ORDER BY a.token_expires_at NULLS LAST
  LIMIT 20;
"
```

Agency API:

```bash
curl -s -b cookies.txt "https://pttads.vn/api/v1/clients/<UUID>/channel-accounts" | jq '.accounts[] | select(.channel==\"meta\")'
```

## Alert

- Job refresh → inbox `meta_token` qua `notify_agency_ops`
- Env: `PTT_META_TOKEN_ALERT_DAYS=7`, `PTT_AGENCY_TOKEN_ALERT_EMAIL`, `SLACK_WEBHOOK_URL`
- Sentry: tag `meta_token_refresh` (xem [sentry-phase2-dashboards.md](./sentry-phase2-dashboards.md))

## Rollback / khắc phục

| Tình huống | Cách xử lý |
|------------|------------|
| Token revoked | User re-auth Meta Business → paste token mới trên UI |
| Vault key lost | **Không decrypt được** — phải nhập lại token tất cả accounts |
| Refresh job DLQ | `job_queue` status=dead → fix token → re-enqueue |

## Liên quan

- Insights replay: [meta-insights-replay.md](./meta-insights-replay.md)
- Closed-loop pilot: `./scripts/staging_closed_loop_pilot.sh --sync`
- Write cutover: [cutover-leads-write-phase2.md](./cutover-leads-write-phase2.md)

---

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-17 | Phase 2 Meta token refresh runbook |
