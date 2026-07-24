# B9 Tracking — Pilot rollout & 30-day soak

> **Phạm vi:** CAPI Conversion OS pilot trên 1–2 clients · soak ≥30 ngày trước widen prod  
> **Env template:** [`deploy/env.meta-enterprise-b9.example`](../deploy/env.meta-enterprise-b9.example)

---

## Phase 1 — Staging / dev

1. Apply DDL v5:
   ```bash
   ./scripts/apply_pg_ddl_v5_meta_conversion.sh
   ```
2. Bật stub + tracking trên API và ops-web:
   ```bash
   PTT_META_TRACKING_ENABLED=1
   PTT_CAPI_STUB=1
   NEXT_PUBLIC_PTT_META_TRACKING_ENABLED=1
   ```
3. Gate nhanh (bỏ build/e2e/soak):
   ```bash
   WAVE_B9_SKIP_BUILD=1 WAVE_B9_SKIP_JEST=1 WAVE_B9_SKIP_E2E=1 WAVE_B9_SKIP_SOAK=1 \
     ./scripts/wave_b9_gate.sh
   ```
4. Playwright E2E-M4 (Nest + ops-web đang chạy):
   ```bash
   WAVE_B9_SKIP_E2E=0 ./scripts/playwright_ops_meta_tracking_e2e.sh
   ```

---

## Phase 2 — Pilot 1–2 clients (real CAPI)

### Preflight

```bash
# .env — ví dụ 1 client pilot
PTT_META_TRACKING_ENABLED=1
PTT_CAPI_ENABLED=1
PTT_CAPI_STUB=0
PTT_CAPI_PILOT_CLIENTS=<uuid-client-1>   # hoặc uuid1,uuid2
NEXT_PUBLIC_PTT_META_TRACKING_ENABLED=1

./scripts/b9_tracking_pilot_preflight.sh
```

Checklist thủ công:

- [ ] Pixel ID + access token trên `client_channel_accounts` (channel `meta`)
- [ ] Test pixel OK trên `/meta/tracking`
- [ ] Launch QA run có 4 mục meta auto-sync
- [ ] Hub map ≥80% spend (unmapped ≤20%)

### Smoke hàng ngày

```bash
export B9_SMOKE_CLIENT_ID=<pilot-uuid>
./scripts/wave_b9_smoke.sh
```

### Soak 30 ngày

Ghi snapshot mỗi ngày (cron 06:05):

```cron
5 6 * * * cd /var/www/ptt && set -a && source .env && set +a && ./scripts/b9_tracking_soak_record.sh
```

Đánh giá sau ≥30 mẫu / 30 ngày:

```bash
PTT_B9_SOAK_DAYS=30 PTT_B9_SOAK_MIN_SAMPLES=28 \
  python3 -m ptt_crm.b9_tracking_soak_evidence evaluate
```

Hoặc trong gate đầy đủ:

```bash
WAVE_B9_SKIP_SOAK=0 ./scripts/wave_b9_gate.sh
```

**Ngưỡng mặc định soak** (`b9_tracking_soak_evidence.py`):

| Metric | Ngưỡng |
|--------|--------|
| CAPI fail rate 24h | ≤ `PTT_B9_SOAK_MAX_FAIL_RATE_PCT` (default 10%) |
| CAPI sent 24h (pilot) | ≥ `PTT_B9_SOAK_MIN_SENT_24H` (default 1) |
| Span | ≥ 30 ngày, ≥ 28 snapshots |

Artifact: `.local-dev/b9-tracking-soak-evidence.jsonl`

---

## Phase 3 — Widen prod

Sau soak PASS:

1. Xóa dần `PTT_CAPI_PILOT_CLIENTS` (hoặc mở rộng allowlist)
2. `PTT_META_CONVERSION_SYNC_ENABLED=1` — bật backfill hourly
3. `PTT_META_ALERTS_ENABLED=1` — bật alerts B8+B9 trên staging trước
4. Regression:
   ```bash
   ./scripts/wave_b9_gate.sh          # full gate
   WAVE_B9_SKIP_B8_GATE=0 ...       # khi B8 đã merge
   WAVE_B9_SKIP_HORIZON1=0 ...      # horizon1 meta gates
   ```

---

## Regression matrix (Sprint H)

| Gate | Script | Skip env |
|------|--------|----------|
| B9 full | `./scripts/wave_b9_gate.sh` | `WAVE_B9_SKIP_*` |
| B9 smoke | `./scripts/wave_b9_smoke.sh` | — |
| B8 regression | trong `wave_b9_gates` G11 | `WAVE_B9_SKIP_B8_GATE=1` |
| Horizon 1 | trong `wave_b9_gates` G12 | `WAVE_B9_SKIP_HORIZON1=1` (default dev) · `=0` release |
| E2E-M4 | `playwright_ops_meta_tracking_e2e.sh` | `WAVE_B9_SKIP_E2E=1` (default) |

---

## Troubleshooting

| Triệu chứng | Hướng xử lý |
|-------------|-------------|
| `/meta/tracking` 404 / trống nav | `NEXT_PUBLIC_PTT_META_TRACKING_ENABLED=1` + rebuild ops-web |
| health `disabled` | `PTT_META_TRACKING_ENABLED=1` trên Nest |
| test-pixel fail | `PTT_CAPI_STUB=1` staging; prod cần token + pixel |
| Launch QA không launch_ready | Mở `/meta/tracking` → preflight; sync meta bridge |
| soak `no_records` | Chạy `b9_tracking_soak_record.sh` daily ≥30d |
