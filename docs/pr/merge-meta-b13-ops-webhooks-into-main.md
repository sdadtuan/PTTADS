# Merge PR — Meta Enterprise B13: Ops webhooks (account disabled alert)

## Summary

- Parse Meta ops webhook events on existing `POST /api/v1/webhooks/meta` (Nest)
- Insert deduped rows into `meta_alerts`:
  - `meta_account_disabled` — ad account status ≠ ACTIVE
  - `ad_disapproved` — ad `effective_status = DISAPPROVED`
- Worker job type `meta_ops_webhook` for async/replay
- Hub inline danger alert + Meta alerts tab labels when `PTT_META_ALERTS_ENABLED=1`

## Flag

| Env | Default | Wave |
|-----|---------|------|
| `PTT_META_OPS_WEBHOOKS` | `0` | B13 |
| `PTT_META_ALERTS_ENABLED` | (existing) | B8 — required for hub badge |

See `deploy/env.meta-enterprise-b13.example`.

## Files (high level)

| Area | Path |
|------|------|
| Python parser + insert | `ptt_meta/ops_webhooks.py` |
| Worker | `ptt_jobs/handlers/meta_ops_webhook.py`, `ptt_worker/__main__.py` |
| Nest | `services/ptt-crm-api/src/webhooks/meta-ops-webhook.*` |
| Webhook integration | `webhooks.service.ts`, `meta-webhook.repository.ts` |
| Hub UI | `MetaAlertsTable.tsx`, `agency.service.ts` |
| Gates | `ptt_crm/wave_b13_gates.py`, `scripts/wave_b13_gate.sh` |

## Test plan

- [ ] `./scripts/wave_b13_gate.sh` — B13-G01..G06 PASS
- [ ] `./scripts/wave_b13_smoke.sh` — fixture parse + stub
- [ ] `cd services/ptt-crm-api && npm test -- --testPathPattern=meta-ops-webhook`
- [ ] `cd services/ptt-crm-api && npm run build`
- [ ] `cd services/ops-web && npm run build`
- [ ] Pilot: simulate account disabled webhook → open alert in hub within 15min (with flags on + PG)

## DoD (spec §18 B13)

Simulated account disabled → alert + hub badge within 15min when:

1. `PTT_META_OPS_WEBHOOKS=1`
2. `PTT_META_ALERTS_ENABLED=1`
3. `meta_alerts` table present (DDL v4)
4. Client resolved via `client_channel_accounts.external_account_id`
