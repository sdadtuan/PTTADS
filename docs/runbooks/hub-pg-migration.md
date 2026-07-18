# Hub PG migration (Phase 3 Track D)

## Prerequisites

- Phase 2 write soak ≥ 30d (recommended)
- `./scripts/apply_pg_ddl_v4_hub_sop.sh`

## Steps

### 1. Apply DDL v4

```bash
./scripts/apply_pg_ddl_v4_hub_sop.sh
```

### 2. One-way SQLite → PG backfill

```bash
export PTT_SQLITE_PATH=/var/www/ptt/ptt.db
python3 scripts/migrate_sqlite_hub_sop_to_pg.py
```

Verify:

```sql
SELECT COUNT(*) FROM hub_campaigns;
SELECT COUNT(*) FROM sop_templates;
```

### 3. Dual-read (staging)

```bash
# Read PG, SQLite writes still OK
export PTT_HUB_READ_SOURCE=0
export PTT_SOP_READ_SOURCE=0
# Smoke Flask Hub + SOP UI
```

### 4. Cutover read to PG

```bash
export PTT_HUB_READ_SOURCE=1
export PTT_SOP_READ_SOURCE=1
sudo systemctl restart ptt.service
```

Hub list API uses `ptt_crm.hub_pg_read` when flag on.

### 5. Hub map

`hub_campaign_map` already PG-primary (Phase 2). Extend `channel=google` via Agency UI.

## Rollback

```bash
export PTT_HUB_READ_SOURCE=0
export PTT_SOP_READ_SOURCE=0
sudo systemctl restart ptt.service
```

SQLite data unchanged — PG is additive until write cutover (Phase 4).
