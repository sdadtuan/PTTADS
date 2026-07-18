# Lead shadow sync sunset (Phase 3 Track D4)

## Criteria (all required)

- [ ] Phase 2 write cutover stable ≥ 30 days
- [ ] `write-soak-evidence.jsonl` — 0 mismatch in window
- [ ] No rollback drill failure in 30d
- [ ] Flask lead reads use Nest/PG (`PTT_LEADS_READ_UPSTREAM=nest` or PG direct)

## Sunset steps

1. **Freeze shadow dependency audit**

```bash
rg -l "PTT_LEAD_SHADOW_SYNC|lead_shadow" --type py
```

2. **Disable timer (staging first)**

```bash
sudo systemctl stop ptt-lead-shadow-sync.timer
sudo systemctl disable ptt-lead-shadow-sync.timer
```

3. **Set flag prod**

```bash
# /var/www/ptt/.env
PTT_LEAD_SHADOW_SYNC=0
sudo systemctl restart ptt.service ptt-lead-shadow-sync.service
```

4. **Monitor 48h**

- Sentry: no spike in lead read errors
- Nest `GET /api/v1/leads` p95 unchanged
- AM spot-check 5 clients

## Rollback

```bash
PTT_LEAD_SHADOW_SYNC=1
sudo systemctl enable --now ptt-lead-shadow-sync.timer
./scripts/sync_lead_shadow.sh
```

Shadow repopulates SQLite from PG — no data loss if PG is source of truth.
