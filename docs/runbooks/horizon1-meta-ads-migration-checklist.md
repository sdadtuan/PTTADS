# Horizon 1 — Meta / Facebook Ads migration checklist

> **Mục tiêu:** Migrate kênh Meta Ads khỏi Flask admin (`/crm/facebook-ads`) sang ops-web + Nest, webhook Nest-only, autosync standalone — tương tự Horizon 0 (SEO + Email).

**Phạm vi:** Hub UI staff, webhook lead ingest, autosync daemon, nginx redirect. **Không** stop `ptt.service` (CRM legacy vẫn chạy).

**Tham chiếu:** [`SPEC_MIGRATION_FLASK_EXECUTION_PLAN.md`](../SPEC_MIGRATION_FLASK_EXECUTION_PLAN.md) · [`horizon0-gate-a-execution.md`](./horizon0-gate-a-execution.md)

---

## Quick commands

```bash
cd /path/to/PTTADS
cp deploy/env.horizon1-meta-ads.example .env.horizon1   # chỉnh secrets trên VPS
set -a && source .env.horizon1 && set +a

chmod +x scripts/horizon1_meta_ads_pack.sh scripts/horizon1_meta_ads_soak_record.sh

# 1) Preflight (CI / staging)
./scripts/horizon1_meta_ads_pack.sh preflight

# 2) Prod soak — cron mỗi ngày ≥7 ngày
./scripts/horizon1_meta_ads_pack.sh soak

# 3) Evaluate + merge signoff
./scripts/horizon1_meta_ads_pack.sh evaluate

# Staging shortcut (bootstrap 7d soak — KHÔNG dùng prod):
HORIZON1_BOOTSTRAP_SOAK=1 ./scripts/horizon1_meta_ads_pack.sh full

# Local/CI — chạy M1-A..F automation (staging sign-off):
./scripts/horizon1_meta_ads_pack.sh execute-local

# Pilot metrics (M1-E):
./scripts/generate_horizon1_meta_metrics.sh 28

# 4) Apply nginx + env (dry-run → APPLY=1)
sudo -E ./scripts/close_flask_retirement_meta_ads.sh
sudo -E APPLY=1 ./scripts/close_flask_retirement_meta_ads.sh
```

**Artifacts:**

| File | Ý nghĩa |
|------|---------|
| `.local-dev/horizon1-meta-ads-gate-report.json` | Automated gates M1-G01…G09 |
| `.local-dev/horizon1-meta-ads-soak-evidence.jsonl` | Daily soak snapshots |
| `.local-dev/horizon1-meta-ads-signoff.json` | Merged gate + soak |
| `docs/evidence/horizon1-meta-ads-signoff.json` | Human sign-off (copy từ template) |

---

## Trạng thái hiện tại vs mục tiêu

| Thành phần | Hiện tại | Mục tiêu Horizon 1 |
|------------|----------|---------------------|
| Hub UI staff | Flask `/crm/facebook-ads` + ops-web `/meta/facebook-ads` | ops-web canonical; Flask redirect |
| Webhook Meta | Env-dependent Flask fallback | Nest-only (`PTT_WEBHOOKS_NEST_META=1`) |
| Autosync | `ptt-fb-autosync.service`, import `app.get_connection` | Standalone PG; không phụ thuộc Gunicorn |
| Campaign writes | Nest + Temporal | Giữ nguyên; optional write pilot |
| Insights sync | `ptt_worker` / `meta_insights_sync` | Không đổi |
| Portal client | Read-only Meta KPI | Verify sau cutover |

---

## A. Prerequisites (M1-A)

- [ ] **A1** PostgreSQL: `client_channel_accounts`, `daily_performance`, `job_queue`, Meta DDL applied
- [ ] **A2** Nest API: `GET /api/v1/facebook-ads/hub` + RBAC `crm_facebook_ads` (`StaffFacebookAdsViewGuard`)
- [ ] **A3** ops-web: `services/ops-web/src/app/meta/facebook-ads/page.tsx` deploy lên `ops.pttads.vn`
- [ ] **A4** Staff permissions seeded: `python3 scripts/seed_staff_meta_permissions.py` (hoặc tương đương)
- [ ] **A5** `ptt-fb-autosync.service` + `ptt_worker` active; Meta token refresh OK
- [ ] **A6** Meta App webhook URL trỏ Nest: `https://api.pttads.vn/webhooks/meta` (verify subscription)
- [ ] **A7** Preflight PASS: `./scripts/horizon1_meta_ads_pack.sh preflight`

**Gate IDs:** M1-G01 (pytest), M1-G02 (ops-web page), M1-G03 (Nest hub route)

---

## B. Staged cutover (M1-B)

Thực hiện **theo thứ tự** — không nhảy bước trên prod.

### B1 — Webhooks Nest-only

| # | Task | Env / verify |
|---|------|--------------|
| B1.1 | Bật Nest Meta webhook | `PTT_WEBHOOKS_NEST_ENABLED=1`, `PTT_WEBHOOKS_NEST_META=1` |
| B1.2 | Tắt Flask fallback | `PTT_WEBHOOKS_FLASK_FALLBACK=0` |
| B1.3 | Restart Nest | `systemctl restart ptt-crm-api` |
| B1.4 | Meta Developer Console → Test webhook | Lead event → row trong `job_queue` (`lead%`) |
| B1.5 | Monitor 24h | Không lead miss; worker consume OK |

- [ ] B1 complete — **Gate M1-G04** PASS

### B2 — Autosync standalone (không chạy trong Gunicorn)

| # | Task | Verify |
|---|------|--------|
| B2.1 | `CRM_FACEBOOK_BACKGROUND=1` | Background thread Flask OFF |
| B2.2 | `CRM_FACEBOOK_BACKGROUND_IN_GUNICORN=0` | Không duplicate sync |
| B2.3 | Confirm `ptt-fb-autosync.service` running | `systemctl status ptt-fb-autosync` |
| B2.4 | **Refactor** `crm_facebook_autosync.py` | Dùng `ptt_jobs.db.pg_connection` thay `app.get_connection` |
| B2.5 | Remove `After=ptt.service` nếu decouple xong | Autosync survive Flask restart |

- [ ] B2 complete — **Gate M1-G07** PASS (warn nếu vẫn `app import`)

### B3 — Hub admin ops-web canonical

| # | Task | Verify |
|---|------|--------|
| B3.1 | Staff dùng `https://ops.pttads.vn/meta/facebook-ads` ≥1 tuần pilot | CPL summary, campaign map |
| B3.2 | UAT: filter client, date range, export | Manual checklist §E |
| B3.3 | `PTT_FLASK_META_ADS_ADMIN_RETIRED=1` trên VPS | Gate M1-G09 |
| B3.4 | nginx redirect | `/crm/facebook-ads` → ops-web (**Gate M1-G06**) |
| B3.5 | Dry-run retire script | `sudo -E ./scripts/close_flask_retirement_meta_ads.sh` |
| B3.6 | Apply prod | `sudo -E APPLY=1 ./scripts/close_flask_retirement_meta_ads.sh` |

- [ ] B3 complete — bookmark Flask hub → 302 ops-web

### B4 — Campaign write pilot (optional)

Chỉ khi agency bật Temporal campaign writes cho pilot client.

| # | Task | Env |
|---|------|-----|
| B4.1 | Enable write flag | `PTT_META_CAMPAIGN_WRITE_ENABLED=1` |
| B4.2 | Pilot campaign allowlist | `PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS=<id>` |
| B4.3 | Approve flow smoke | ops-web → Nest → Temporal → Meta API |
| B4.4 | Rollback plan documented | Tắt flag + revert ad set |

- [ ] B4 complete (optional)

**Staged flags trong signoff:** `docs/evidence/horizon1-meta-ads-signoff.template.json` → `staged_steps`

---

## C. Soak ≥7 ngày (M1-C)

Tương tự Horizon 0 SEO/Email soak.

| # | Task |
|---|------|
| C1 | Cron daily: `./scripts/horizon1_meta_ads_soak_record.sh` |
| C2 | Snapshot ghi: webhook flags, `lead_jobs_24h`, `meta_perf_rows_7d`, `meta_tokens_active` |
| C3 | ≥7 samples, span ≥7 ngày, `ok: true` mỗi dòng |
| C4 | `./scripts/horizon1_meta_ads_pack.sh evaluate` → `soak_7d_ok: true` |

**Gate:** M1-G08 · **KHÔNG** dùng `HORIZON1_BOOTSTRAP_SOAK=1` trên prod.

Prod cron example:

```cron
5 6 * * * cd /var/www/ptt && set -a && source .env && set +a && ./scripts/horizon1_meta_ads_soak_record.sh
```

---

## D. Flask admin retirement — Meta hub only (M1-D)

Partial retire — **không** stop `ptt.service`.

```bash
sudo -E ./scripts/close_flask_retirement_meta_ads.sh        # dry-run
sudo -E APPLY=1 ./scripts/close_flask_retirement_meta_ads.sh
```

Verify sau apply:

- [ ] `curl -I https://rs.pttads.vn/crm/facebook-ads` → `302` → `ops.pttads.vn/meta/facebook-ads`
- [ ] Flask CRM routes khác (`/crm/leads`, …) vẫn 200
- [ ] `.local-dev/horizon1-meta-ads-gate-report.json` → `ok: true`

nginx block (trong `deploy/nginx-rs-delivery-admin-retired.conf`):

```nginx
location ^~ /crm/facebook-ads {
    return 302 https://ops.pttads.vn/meta/facebook-ads;
}
```

Full Flask stop: chỉ sau CRM cutover — [`phase5-flask-retirement-checklist.md`](./phase5-flask-retirement-checklist.md)

---

## E. Manual UAT checklist

Điền vào `docs/evidence/horizon1-meta-ads-signoff.json` → `manual_uat`.

| # | Scenario | Pass |
|---|----------|------|
| E1 | Staff login ops-web → Meta hub loads CPL + spend | ☐ |
| E2 | Meta test webhook → lead trong CRM ≤5 phút | ☐ |
| E3 | Single autosync process (không duplicate trong Gunicorn) | ☐ |
| E4 | Client portal Meta tab read-only, số khớp hub | ☐ |
| E5 | Campaign write approve smoke (nếu B4) | ☐ |

---

## F. Pilot metrics & case study (M1-E)

Reuse Horizon 0 pilot exporter (Meta CPL đã có):

```bash
export HORIZON0_PILOT_CLIENTS='<uuid>:<customer_id>:Client A'
./scripts/generate_horizon0_case_studies.sh 28
```

Hoặc query trực tiếp signoff fields:

| Metric | Nguồn |
|--------|-------|
| `meta_spend_vnd` | `daily_performance` channel=meta |
| `meta_leads_crm` | CRM leads source=meta |
| `meta_cpl_vnd` | spend / leads |
| `webhook_ingest_24h` | soak snapshot `lead_jobs_24h` |

- [ ] F1 Pilot client ≥28 ngày data
- [ ] F2 CPL baseline vs post-migration documented
- [ ] F3 Case study narrative (Challenge / Approach / Result)

---

## G. Sign-off (M1-F)

**Automated Gate M1 =** `.local-dev/horizon1-meta-ads-signoff.json` với `ok: true`

**Human sign-off** → `docs/evidence/horizon1-meta-ads-signoff.json`:

| Role | Field |
|------|-------|
| Head Media | `signoffs.head_media` |
| QA / Compliance | `signoffs.qa_compliance` |
| AM pilot | `signoffs.am_pilot` |
| DevOps | `signoffs.devops` |

Copy template:

```bash
cp docs/evidence/horizon1-meta-ads-signoff.template.json docs/evidence/horizon1-meta-ads-signoff.json
```

Sau khi ký → cập nhật SPEC agency Gate M1 → ✅

---

## H. VPS prod sequence (recommended)

| Day | Action |
|-----|--------|
| D0 | Preflight PASS; B1 webhooks Nest-only; monitor 24h |
| D1 | B2 autosync standalone; B3 staff pilot ops-web hub |
| D2 | Dry-run `close_flask_retirement_meta_ads.sh`; APPLY nginx + env |
| D2–D9 | Daily `./scripts/horizon1_meta_ads_pack.sh soak` |
| D9 | `./scripts/horizon1_meta_ads_pack.sh evaluate` |
| D9 | B4 campaign write (optional); pilot metrics + case study |
| D10 | Human sign-off JSON; Gate M1 ✅ |

---

## I. Rollback plan

| Bước lỗi | Rollback |
|----------|----------|
| Webhook miss leads | `PTT_WEBHOOKS_FLASK_FALLBACK=1` tạm; fix Nest routing |
| Hub ops-web broken | Gỡ nginx redirect; staff dùng Flask tạm |
| Autosync duplicate | `CRM_FACEBOOK_BACKGROUND_IN_GUNICORN=0`; stop duplicate unit |
| Campaign write incident | `PTT_META_CAMPAIGN_WRITE_ENABLED=0` |

---

## J. Gate reference (automated)

| ID | Check |
|----|-------|
| M1-G01 | pytest Meta regression |
| M1-G02 | ops-web Meta hub page exists |
| M1-G03 | Nest `/api/v1/facebook-ads/hub` |
| M1-G04 | Webhook Nest Meta, no Flask fallback |
| M1-G05 | Nest hub smoke (health + hub API) |
| M1-G06 | nginx `/crm/facebook-ads` redirect |
| M1-G07 | Autosync standalone (warn if `app` import) |
| M1-G08 | Soak ≥7d |
| M1-G09 | `PTT_FLASK_META_ADS_ADMIN_RETIRED` |
| M1-G11 | Meta retirement dry-run preflight artifact |

---

## K. Mapping Horizon 0 ↔ Horizon 1

| Horizon 0 (SEO/Email) | Horizon 1 (Meta Ads) |
|----------------------|----------------------|
| `horizon0_gate_a_pack.sh` | `horizon1_meta_ads_pack.sh` |
| Phase 5 + EM-5 gates | `horizon1_meta_ads_gates.py` |
| SEO/Email soak jsonl | `horizon1-meta-ads-soak-evidence.jsonl` |
| `close_flask_retirement_delivery_admin.sh` | `close_flask_retirement_meta_ads.sh` |
| `/crm/seo`, `/crm/email` redirect | `/crm/facebook-ads` redirect |
| Gate A signoff | `horizon1-meta-ads-signoff.json` |

---

## L. Out of scope (Horizon 2+)

- Full CRM Flask retirement (`/crm/leads`, contracts, …)
- Stop `ptt.service`
- Meta creative studio / bulk editor greenfield
- Multi-ad-account MCC at scale
