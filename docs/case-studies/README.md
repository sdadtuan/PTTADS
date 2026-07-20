# Horizon 0 — Pilot case studies

Generated metrics for Gate A sales / sign-off evidence.

| Pilot | Headline | File |
|-------|----------|------|
| Pilot 1 (configure HORIZON0_PILOT_CLIENTS) | Metrics pending — configure pilot IDs | [pilot-1.md](./pilot-1.md) |

## Regenerate

```bash
export DATABASE_URL=postgresql://...
export HORIZON0_PILOT_CLIENTS='uuid:customer_id:Client Name,uuid2:cid2:Client 2'
./scripts/generate_horizon0_case_studies.sh
```
