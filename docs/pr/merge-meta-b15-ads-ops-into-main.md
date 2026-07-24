# Merge PR — Meta Enterprise B15: Ads Ops UI

## Summary

- Nest `meta-ads-ops` module: templates, preflight, creative upload, launch submit, edit snapshot/diff/submit, deep-link
- ops-web `/meta/ads-ops`: Launch wizard (5 steps) + Edit wizard (4 steps) with `MetaWizardStepper`, `MetaCreativePicker`, diff review
- Hub **Edit ad** entry from disapproved alerts and creative registry links
- Python helpers: `ptt_meta/ads_ops.py`, `creative_upload.py`, `ads_edit.py`
- Extends `campaign_write_requests` with `create_*` and `update_ad_*` change types

## Flags

| Env | Default | Wave |
|-----|---------|------|
| `PTT_META_ADS_OPS_ENABLED` | `0` | B15 (Nest + worker) |
| `PTT_META_ADS_OPS_PILOT_CLIENTS` | empty | B15 pilot allowlist |
| `NEXT_PUBLIC_PTT_META_ADS_OPS_ENABLED` | `0` | B15 (ops-web) |

See `deploy/env.meta-enterprise-b15.example`.

## DoD (spec §18 B15)

1. Launch wizard submits governed `create_campaign` write after preflight
2. Edit tab loads snapshot, shows diff, submits `update_ad_creative` / `update_ad_copy`
3. Disapproved ad requires ack checkbox before edit submit
4. Hub alerts tab links to `/meta/ads-ops?mode=edit&…`

## Test plan

- [ ] `./scripts/wave_b15_gate.sh` — B15-G01..G06 PASS
- [ ] `./scripts/wave_b15_smoke.sh`
- [ ] `cd services/ptt-crm-api && npm test -- --testPathPattern=meta-ads-ops`
- [ ] `cd services/ptt-crm-api && npm run build`
- [ ] `cd services/ops-web && npm run build`
- [ ] Pilot: enable flags + add client to `PTT_META_ADS_OPS_PILOT_CLIENTS`
