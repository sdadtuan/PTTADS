# Horizon 0 — Gate A execution runbook

> **Mục tiêu:** Ký Gate A SEO + Email prod pilot, retire Flask admin SEO/Email, xuất 1–2 case study có số.

## Quick commands

```bash
cd /path/to/PTTADS
cp deploy/env.horizon0-gate-a.example .env.horizon0   # chỉnh secrets trên VPS
set -a && source .env.horizon0 && set +a

# 1) Preflight (CI / staging)
chmod +x scripts/horizon0_gate_a_pack.sh
./scripts/horizon0_gate_a_pack.sh preflight

# 2) Prod soak — chạy cron mỗi ngày ≥7 ngày
./scripts/horizon0_gate_a_pack.sh soak

# 3) Evaluate + merge signoff JSON
./scripts/horizon0_gate_a_pack.sh evaluate

# Staging shortcut (bootstrap 7d soak — KHÔNG dùng trên prod):
HORIZON0_BOOTSTRAP_SOAK=1 ./scripts/horizon0_gate_a_pack.sh full
```

## A. Gate A SEO (Phase 5)

Checklist đầy đủ: [`phase5-prod-signoff-checklist.md`](./phase5-prod-signoff-checklist.md)

1. Apply DDL + `SEO_AEO_DB=pg` soak ≥7 ngày
2. `./scripts/phase5_prod_cutover_gate.sh` → `.local-dev/phase5-gate-report.json`
3. Portal E2E (trước bật portal prod): `./scripts/phase5_portal_seo_e2e_gate.sh`
4. Human sign-off → `docs/evidence/phase5-prod-signoff.json`

## B. Gate A Email (EM-5)

Checklist: [`email-marketing-prod-pilot-checklist.md`](./email-marketing-prod-pilot-checklist.md)

1. `./scripts/apply_pg_ddl_email_mkt_em12.sh` (nếu chưa)
2. `python3 scripts/seed_staff_email_mkt_permissions.py`
3. Real ESP: copy `deploy/env.em5-prod-send.example` → VPS `.env`
4. Enable timers: `ptt-email-campaign-schedule`, `ptt-email-soak`
5. `./scripts/phase5_email_prod_pilot_gate.sh` → `.local-dev/phase5-email-pilot-gate-report.json`
6. Human sign-off → `docs/evidence/em5-email-pilot-signoff.json`

## C. Flask retirement — SEO + Email admin only (Phase 5 partial)

Không stop `ptt.service` — chỉ redirect nginx + env flags.

```bash
sudo -E ./scripts/close_flask_retirement_delivery_admin.sh        # dry-run
sudo -E APPLY=1 ./scripts/close_flask_retirement_delivery_admin.sh
```

Verify:

- `https://rs.pttads.vn/crm/seo` → 302 `ops.pttads.vn/seo/hub`
- `https://rs.pttads.vn/crm/email` → 302 `ops.pttads.vn/email/hub`
- Gate: `.local-dev/phase5-delivery-admin-retirement-gate-report.json`

Full Flask stop (sau CRM cutover): [`phase5-flask-retirement-checklist.md`](./phase5-flask-retirement-checklist.md)

**Tiếp theo (Horizon 1):** Meta / Facebook Ads — [`horizon1-meta-ads-migration-checklist.md`](./horizon1-meta-ads-migration-checklist.md)

## D. Pilot case studies

```bash
export HORIZON0_PILOT_CLIENTS='<client_uuid>:<customer_id>:Client A,<uuid2>:<cid2>:Client B'
./scripts/generate_horizon0_case_studies.sh 28
```

Output:

- `.local-dev/horizon0-pilot-case-studies.json`
- `docs/case-studies/pilot-1.md`, `pilot-2.md`

Điền narrative (Challenge / Approach / Result) sau khi có số thật từ pilot.

## E. Horizon 0 sign-off artifact

Merged report: `.local-dev/horizon0-gate-a-signoff.json`

| Field | Meaning |
|-------|---------|
| `seo_gate_ok` | Phase 5 pytest + flags |
| `email_gate_ok` | EM-5 gate pack |
| `delivery_admin_retire_ok` | ops-web hubs + nginx |
| `seo_soak_ok` / `email_soak_ok` | ≥7 daily samples, 0 failures |

**Prod Gate A = `ok: true` + human signoffs filled in evidence JSON.**

## F. VPS prod sequence (recommended)

| Day | Action |
|-----|--------|
| D0 | Preflight gates PASS; staged cutover B1–B4 (email); governance ON (SEO) |
| D0 | `delivery-admin` nginx apply; ESP real send 1 campaign test |
| D1–D7 | Daily `./scripts/horizon0_gate_a_pack.sh soak` |
| D7 | `./scripts/horizon0_gate_a_pack.sh evaluate`; generate case studies |
| D7 | Human sign-off JSON; update SPEC Gate A → ✅ |
