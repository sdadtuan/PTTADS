# Runbook — Meta insights replay (Phase 2 M2)

> **Mục tiêu:** Backfill / replay `daily_performance` khi sync fail hoặc cần đối soát T-1 data.

## Khi nào replay

- `meta_insights_sync_state.last_error` khác NULL
- Pilot client thiếu CPL tab sau cutover
- Token vừa refresh — cần sync lại N ngày
- Alert Meta insights sync fail (inbox + Sentry)

## Systemd (VPS — T-1 hàng ngày)

```bash
sudo cp ptt-meta-insights.service ptt-meta-insights.timer /etc/systemd/system/
sudo systemctl enable --now ptt-meta-insights.timer
# Schedule: 02:00 ICT
```

## Replay một ngày (một client)

```bash
cd /var/www/ptt
set -a && source .env && set +a

export PTT_META_INSIGHTS_SYNC=1
# Staging without Graph API:
# export PTT_META_INSIGHTS_STUB=1

python3 -c "
from ptt_meta.insights_sync import sync_meta_insights
import json
out = sync_meta_insights(
    target_date='2026-07-16',
    client_id='<CLIENT_UUID>',
    compute_metrics=True,
)
print(json.dumps(out, indent=2, default=str))
"
```

Closed-loop pilot (automated gate):

```bash
./scripts/staging_closed_loop_pilot.sh --sync --client-code DEMO
```

## Replay nhiều ngày (backfill)

```bash
FROM=2026-07-10
TO=2026-07-16
CLIENT_ID=<UUID>

python3 <<'PY'
import os
from datetime import date, timedelta
from ptt_meta.insights_sync import sync_meta_insights

start = date.fromisoformat(os.environ["FROM"])
end = date.fromisoformat(os.environ["TO"])
cid = os.environ["CLIENT_ID"]
d = start
while d <= end:
    out = sync_meta_insights(target_date=d, client_id=cid, compute_metrics=True)
    print(d.isoformat(), out.get("ok"), out.get("rows_upserted"))
    d += timedelta(days=1)
PY
```

## Worker job (queue)

```bash
python3 -c "
from ptt_jobs.enqueue import enqueue_job
enqueue_job(
    'meta_insights_sync',
    {'target_date': '2026-07-16', 'client_id': '<UUID>', 'compute_metrics': True},
    'meta_insights:2026-07-16:<UUID>',
)
"
python3 -m ptt_worker --once
```

## Verify

```bash
psql "$DATABASE_URL" -c "
  SELECT client_id, performance_date, COUNT(*) rows, SUM(spend) spend
  FROM daily_performance
  WHERE channel = 'meta'
  GROUP BY 1, 2
  ORDER BY 2 DESC
  LIMIT 10;
"

# CPL/ROAS metrics snapshots
psql "$DATABASE_URL" -c "
  SELECT kpi_code, COUNT(*) FROM metrics_snapshots
  WHERE channel = 'meta' AND period_start >= CURRENT_DATE - 7
  GROUP BY 1;
"
```

Agency UI: Client → tab **Campaign CPL** — rows > 0, `latest_performance_date` = T-1.

## Hub map prerequisite

Insights join campaign qua `hub_campaign_map`. Nếu CPL trống:

```bash
./scripts/sync_hub_campaign_map.sh
psql "$DATABASE_URL" -c "
  SELECT hub_campaign_id, external_campaign_id, target_cpl_vnd, active
  FROM hub_campaign_map WHERE client_id = '<UUID>' AND channel = 'meta';
"
```

Stub campaign (staging): `external_campaign_id = stub_campaign_1`

## Failure alert

Sync partial fail → `notify_agency_ops` + Sentry (`meta_insights` category).  
Xem `meta_insights_sync_state`:

```bash
psql "$DATABASE_URL" -c "SELECT * FROM meta_insights_sync_state WHERE id = 1;"
```

## Liên quan

- Token refresh: [meta-token-refresh.md](./meta-token-refresh.md)
- Phase 2 gate pack: `./scripts/staging_phase2_gate_pack.sh`
- Sentry: [sentry-phase2-dashboards.md](./sentry-phase2-dashboards.md)

---

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-17 | Phase 2 insights replay runbook |
