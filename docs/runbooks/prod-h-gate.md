# PROD-H gate — Production hardening (Prod-S4)

Chạy trên **staging** trước sign-off A6/A7 ([`handover/06`](../handover/06-NGHIEM-THU-VA-BAO-CAO.md)).

## Scripts

| Script | Mục đích |
|--------|----------|
| `./scripts/cskh_board_gate.sh` | P0-C — CSKH board route + SLA unit test |
| `./scripts/prod_h_gate.sh` | PROD-H pack — stub audit, webhook error rate, sub-gates |

## Chạy nhanh

```bash
# Chỉ Python gates (không chạy zalo/cskh shell sub-gates)
python3 -m ptt_crm.prod_h_gates --skip-subgates

# Full pack (cần Node + jest cho CSKH gate)
chmod +x scripts/prod_h_gate.sh scripts/cskh_board_gate.sh
./scripts/prod_h_gate.sh
```

## PROD-H checklist

| ID | Kiểm tra | Env / verify |
|----|----------|--------------|
| PROD-H-STUB | Stub flags tắt | `PTT_*_STUB=0`, Nest `ProdHStubAuditService` |
| PROD-H-MON | Webhook job error ≤1% / 24h | `PTT_WEBHOOK_ERROR_RATE_MAX_PCT=1` |
| PROD-H-GATE | CI workflow `prod-h-gates.yml` | GitHub Actions |
| PROD-H-E2E | Handover F1–F7 | `ops-web/e2e/prod-smoke-handover.spec.ts`, `portal-web/e2e/prod-smoke-handover.spec.ts` |
| PROD-H-PEN | Multi-tenant | `tests/test_multi_tenant_pen.py` + `client-offboard.e2e-spec.ts` |

## Webhook health worker

Bật monitor định kỳ:

```bash
export PTT_WEBHOOK_HEALTH_MONITOR=1
# Enqueue job_type=webhook_health_check (payload: {"dry_run": false})
```

Alert gửi qua `notify_agency_ops` khi tỷ lệ failed vượt ngưỡng.

## Production stub audit (Nest)

Trên env production-like (`NODE_ENV=production` hoặc `PTT_PRODUCTION=1`):

- Không bật `PTT_*_STUB`
- Không bật `PTT_CRM_API_AUTH_DISABLED`
- Không bật portal/staff stub users

Để **chặn khởi động** khi vi phạm: `PTT_PROD_STUB_AUDIT_FATAL=1`

## CI

Workflow [`.github/workflows/prod-h-gates.yml`](../../.github/workflows/prod-h-gates.yml) chạy trên PR/push các path liên quan Prod-S4.
