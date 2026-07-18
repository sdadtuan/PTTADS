# Phase 4 kickoff runbook

Phase 4 = **Meta campaign write + Flask sunset + ClickHouse analytics**.

## Prerequisites

- Phase 3 portal + Temporal worker running
- PostgreSQL with v3 DDL applied
- Nest CRM API on `:3001` with `PTT_INTERNAL_API_KEY`

## 1. Apply DDL v5 (campaign writes)

```bash
export DATABASE_URL=postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency
./scripts/apply_pg_ddl_v5_campaign_writes.sh
```

Verify:

```bash
python -c "from ptt_crm.pg_schema import pg_campaign_writes_ready; print(pg_campaign_writes_ready())"
```

## 2. Start stack

```bash
docker compose up -d postgres temporal temporal-ui
./scripts/local_temporal_worker.sh &
./scripts/local_crm_api_up.sh
# Flask agency UI (read paths + Nest proxies)
export PTT_FLASK_MONOLITH_MODE=active   # or readonly after cutover
flask run --port 5000
```

Dev stub for Meta API:

```bash
export PTT_META_CAMPAIGN_WRITE_STUB=1
```

## 3. Smoke — campaign write queue

1. Open agency client detail → tab **Campaign write**
2. Submit daily budget change for a Meta campaign ID
3. Approve from queue → check Temporal UI workflow completes
4. Confirm PG row status `executed`:

```sql
SELECT id, status, executed_at FROM campaign_write_requests ORDER BY created_at DESC LIMIT 5;
```

## 4. Flask read-only cutover

```bash
export PTT_FLASK_MONOLITH_MODE=readonly
```

Expected:

- `POST /api/v1/clients` → 503 `flask_monolith_readonly`
- `POST /api/v1/clients/{id}/campaign-writes` → 200 (Nest proxy)

Full retirement:

```bash
export PTT_FLASK_MONOLITH_MODE=retired
```

## 5. ClickHouse (F4)

```bash
docker compose -f docker-compose.clickhouse.yml up -d
./scripts/clickhouse_init.sh
./scripts/clickhouse_export_e2e.sh      # full PG → CH verify
./scripts/export_domain_events_clickhouse.sh
```

Prod cutover: `docs/runbooks/phase4-prod-cutover-checklist.md`

## 6. CI

Workflow `phase4-scale.yml` runs Nest build, DDL v5, campaign-writes e2e, and workflow/export tests.

## Rollback

| Component | Action |
|-----------|--------|
| Campaign writes | Stop submitting; pending rows stay `pending_approval` |
| Flask | Set `PTT_FLASK_MONOLITH_MODE=active` |
| Meta stub | `PTT_META_CAMPAIGN_WRITE_STUB=1` in dev |
