# Phase 4 production cutover checklist

Flask **readonly**, Meta campaign write **pilot**, ClickHouse export.

## Prerequisites

- [ ] Phase 3 portal + Temporal stable ≥ 7 ngày
- [ ] `campaign_write_requests` DDL v5 chưa apply trên prod
- [ ] Pilot client có Meta token active trên channel account
- [ ] Biết chính xác `client_id` + Meta `campaign_id` pilot

## 1. Staging rehearsal

```bash
export DATABASE_URL=postgresql://...
./scripts/close_phase4_prod_cutover.sh
export APPLY=1 PTT_FLASK_MONOLITH_MODE=readonly ./scripts/close_phase4_prod_cutover.sh
./scripts/clickhouse_export_e2e.sh
cd services/ptt-crm-api && npm run test:e2e -- --testPathPattern=campaign-writes
```

Verify Flask readonly:

```bash
curl -sf -X POST http://127.0.0.1:8002/api/v1/clients -H 'Content-Type: application/json' -d '{}' | jq .
# expect 503 flask_monolith_readonly
```

Verify Nest proxy still works:

```bash
curl -sf http://127.0.0.1:8002/api/v1/clients/<uuid>/campaign-writes
```

## 2. Prod change window

```bash
sudo -E APPLY=1 \
  PTT_FLASK_MONOLITH_MODE=readonly \
  PTT_META_CAMPAIGN_WRITE_STUB=0 \
  PTT_META_CAMPAIGN_WRITE_PILOT=1 \
  PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS=<uuid> \
  PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS=<campaign_id> \
  ./scripts/close_phase4_prod_cutover.sh
```

Restart (if script not root):

```bash
sudo systemctl restart ptt ptt-crm-api ptt-temporal-worker
sudo systemctl enable --now ptt-clickhouse-export.timer
```

## 3. Meta pilot smoke (1 campaign)

```bash
source deploy/env.meta-campaign-write-pilot.example  # fill UUIDs
./scripts/meta_campaign_write_pilot_smoke.sh
```

Confirm:

```sql
SELECT id, status, executed_at, execution_error
FROM campaign_write_requests
ORDER BY created_at DESC LIMIT 3;
```

Temporal UI: workflow `campaign-write-{id}` → `executed`.

## 4. ClickHouse verify

```bash
./scripts/export_domain_events_clickhouse.sh
curl -s 'http://ptt:ptt_dev@127.0.0.1:8123/?query=SELECT+count()+FROM+ptt.domain_events'
```

## 5. Monitor (14 ngày staging readonly soak)

| Signal | Action |
|--------|--------|
| `flask_monolith_readonly` 503 spike | Expected for legacy write attempts |
| `execution_failed` campaign writes | Check Meta token / pilot lists |
| ClickHouse export timer failures | `journalctl -u ptt-clickhouse-export` |

## Rollback

| Component | Action |
|-----------|--------|
| Flask | `PTT_FLASK_MONOLITH_MODE=active` + `systemctl restart ptt` |
| Meta real writes | `PTT_META_CAMPAIGN_WRITE_STUB=1` or `PTT_META_CAMPAIGN_WRITE_PILOT=0` |
| ClickHouse | Disable timer; PG remains source of truth |

## Sign-off

- [ ] Flask readonly verified on prod
- [ ] 1 pilot campaign write executed on Meta
- [ ] ClickHouse export ≥ 1 batch success
- [ ] Nest campaign-writes e2e pass on staging
