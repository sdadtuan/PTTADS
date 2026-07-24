# Merge PR — Meta Enterprise B14: Warehouse BI (ClickHouse + Grafana)

## Summary

- ETL `daily_performance` (meta + google) → ClickHouse `ptt.meta_daily_facts` with 36-month TTL
- Grafana executive dashboard with Meta spend trend (`deploy/grafana/meta-ops-dashboard.json`)
- Nest compliance export API: `GET /api/v1/meta/compliance/export?client_id=`
- Unified cross-channel KPI API: `GET /api/v1/metrics/cross-channel/summary`
- Hourly insights allowlist via `PTT_META_INSIGHTS_HOURLY` + `PTT_META_INSIGHTS_HOURLY_CLIENTS`

## Flags

| Env | Default | Wave |
|-----|---------|------|
| `PTT_META_WAREHOUSE_EXPORT` | `0` | B14 |
| `PTT_META_INSIGHTS_HOURLY` | `0` | B14 |
| `PTT_META_COMPLIANCE_EXPORT_ENABLED` | `1` | B14 (Nest) |
| `PTT_METRICS_CROSS_CHANNEL_ENABLED` | `1` | B14 (Nest) |

See `deploy/env.meta-enterprise-b14.example`.

## DoD (spec §18 B14)

1. ClickHouse row count ≈ PG sample for 7d — `compare_export_parity()` in `ptt_meta/warehouse_export.py`
2. Grafana dashboard renders spend trend — import `meta-ops-dashboard.json`
3. Compliance export JSON validates schema — `export_version: 1.0`, tokens redacted

## Test plan

- [ ] `./scripts/wave_b14_gate.sh` — B14-G01..G06 PASS
- [ ] `./scripts/wave_b14_smoke.sh`
- [ ] `cd services/ptt-crm-api && npm test -- --testPathPattern='meta-compliance|metrics.service'`
- [ ] `cd services/ptt-crm-api && npm run build`
- [ ] Pilot: `./scripts/export_meta_facts_clickhouse.sh` with ClickHouse up + `PTT_META_WAREHOUSE_EXPORT=1`
