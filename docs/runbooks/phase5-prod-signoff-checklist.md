# Phase 5 SEO/AEO — Production sign-off checklist (VPS)

> **Mục tiêu:** Ký Phase 5 Done trên prod sau staged cutover (Governance → Portal SEO → Experiments) và soak ≥ 7 ngày.  
> **Phụ thuộc:** `SEO_AEO_DB=pg` ≥ 7 ngày · GSC/GA4 OAuth pilot OK · Phase 3 portal stable.  
> **Runbook chi tiết:** [`seo-aeo-pg-oauth-uat-cutover.md`](./seo-aeo-pg-oauth-uat-cutover.md) §9–§10 · **Env:** [`deploy/env.phase5-prod.example`](../../deploy/env.phase5-prod.example)

---

## Participants

| Role | Name | Sign-off |
|------|------|----------|
| Head of SEO/AEO | | [ ] |
| QA / Compliance | | [ ] |
| AM (pilot client) | | [ ] |
| Client approver (portal pilot) | | [ ] |
| DevOps | | [ ] |

---

## A. Prerequisites (trước change window)

### A1. Infrastructure

- [ ] VPS: `DATABASE_URL` → PostgreSQL `ptt_agency`
- [ ] `.env`: `SEO_AEO_DB=pg` ≥ 7 ngày (§8 runbook SEO/AEO)
- [ ] PG schema có bảng Phase 5: `seo_governance_*`, `seo_experiments*`, `seo_portal_client_map`
- [ ] Backup: `pg_dump` + copy `.env` trước change window
- [ ] Flask `ptt` + Nest `ptt-crm-api` + `portal-web` healthy

### A2. Pilot identifiers (điền trước khi cutover)

| Biến | Giá trị prod |
|------|----------------|
| `PILOT_CUSTOMER_ID` (CRM) | __________ |
| `PORTAL_CLIENT_UUID` | __________ |
| `PILOT_CONTENT_ID` (client_review test) | __________ |

### A3. Automated gates (staging mirror hoặc prod read-only)

```bash
cd /var/www/ptt
export DATABASE_URL=postgresql://...
export SEO_AEO_DB=pg
export PTT_SEO_GOVERNANCE_ENABLED=1
export PTT_PORTAL_SEO_ENABLED=0
export PTT_SEO_EXPERIMENTS_ENABLED=0

chmod +x scripts/phase5_prod_cutover_gate.sh
./scripts/phase5_prod_cutover_gate.sh
```

- [ ] `.local-dev/phase5-gate-report.json` → `"ok": true`
- [ ] Pytest Phase 5: 14/14 pass (P5-G01)
- [ ] Feature flags khớp prod plan (P5-G02): governance ON, portal OFF, experiments OFF

**Portal E2E (staging, trước bật portal prod):**

```bash
./scripts/phase5_portal_seo_e2e_gate.sh
```

- [ ] `.local-dev/phase5-portal-seo-uat-signoff.json` → `playwright_e2e: true`

---

## B. Staged cutover (prod change window)

> Thứ tự bắt buộc: **Governance → Portal → Experiments**. Không bật cả 3 cùng lúc lần đầu.

### B1. Step 1 — Governance only

```bash
APPLY=1 PHASE5_ENABLE_GOVERNANCE=1 \
  PHASE5_ENABLE_PORTAL=0 \
  PHASE5_ENABLE_EXPERIMENTS=0 \
  sudo -E ./scripts/close_phase5_prod_cutover.sh
```

Verify `.env`:

- [ ] `PTT_SEO_GOVERNANCE_ENABLED=1`
- [ ] `PTT_PORTAL_SEO_ENABLED=0`
- [ ] `PTT_SEO_EXPERIMENTS_ENABLED=0`
- [ ] `sudo systemctl restart ptt` — exit 0

Smoke:

- [ ] `/crm/seo/governance` loads policies + compliance KPIs
- [ ] Hub hiện card **Governance Hub**; **Experimentation** ẩn

### B2. Step 2 — Portal SEO (sau UAT §C)

```bash
python3 scripts/seed_portal_seo_pilot_map.py --apply \
  --client-id <PORTAL_CLIENT_UUID> \
  --customer-id <PILOT_CUSTOMER_ID>

APPLY=1 PHASE5_ENABLE_GOVERNANCE=1 \
  PHASE5_ENABLE_PORTAL=1 \
  PHASE5_ENABLE_EXPERIMENTS=0 \
  PTT_PORTAL_SEO_SERVICE_TOKEN=<shared-secret> \
  PTT_FLASK_MONOLITH_URL=http://127.0.0.1:8002 \
  PHASE5_SKIP_PORTAL_SIGNOFF=0 \
  sudo -E ./scripts/close_phase5_prod_cutover.sh

sudo systemctl restart ptt-crm-api
# portal-web: npm run build && pm2 restart portal-web
```

- [ ] Nest + Flask token khớp (`PTT_PORTAL_SEO_SERVICE_TOKEN`)
- [ ] Portal nav hiện mục SEO
- [ ] Rollback drill: `PTT_PORTAL_SEO_ENABLED=0` → nav ẩn, CRM approve vẫn OK

### B3. Step 3 — Experiments (internal team, optional)

```bash
APPLY=1 PHASE5_ENABLE_GOVERNANCE=1 \
  PHASE5_ENABLE_PORTAL=1 \
  PHASE5_ENABLE_EXPERIMENTS=1 \
  sudo -E ./scripts/close_phase5_prod_cutover.sh
```

- [ ] `/crm/seo/experiments` loads (không redirect về hub)
- [ ] Tạo experiment draft → running → decision (internal smoke)

---

## C. Manual UAT — 5A Governance

| # | Actor | Action | Expected | Pass |
|---|-------|--------|----------|------|
| C1 | Editor | Content thiếu `meta_title`, status `approved` → **Publish** | Modal governance (không `alert`) | [ ] |
| C2 | Editor | Modal liệt kê rule + field thiếu | `metadata_required` + missing fields | [ ] |
| C3 | Editor | Không thấy nút **Ghi đè** | Chỉ **Đóng** | [ ] |
| C4 | Admin (`configure`) | **Ghi đè & thử lại** + lý do | Publish thành công | [ ] |
| C5 | QA | Governance Hub → compliance stats | Pass rate / blocked hiển thị | [ ] |
| C6 | QA | SQL audit | Row trong `seo_governance_overrides` | [ ] |

```sql
SELECT id, evaluation_id, policy_key, actor_id, reason, created_at
FROM seo_aeo.seo_governance_overrides
ORDER BY id DESC LIMIT 5;
```

---

## D. Manual UAT — 5C Portal SEO (nếu Step B2 đã bật)

| # | Role | Action | Expected | Pass |
|---|------|--------|----------|------|
| D1 | viewer | Login → `https://portal.pttads.vn/seo` | KPIs, không nút approve | [ ] |
| D2 | viewer | `/seo/reports` | Read-only, không internal notes | [ ] |
| D3 | viewer | `/seo/content` | Pending list, không approve | [ ] |
| D4 | approver | Approve item governance-compliant | → `approved`, khỏi pending | [ ] |
| D5 | CRM staff | Content detail timeline | Approval actor portal | [ ] |
| D6 | approver | Approve item thiếu QA | Governance block message | [ ] |

API smoke (prod):

```bash
TOKEN=$(curl -sf -X POST https://portal.pttads.vn/api/v1/portal/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"<approver>","password":"***"}' | jq -r .token)

curl -sf -H "Authorization: Bearer $TOKEN" \
  https://portal.pttads.vn/api/v1/portal/seo/summary | jq .
```

- [ ] D1–D6 pass trên pilot client
- [ ] TLS valid · không lộ service token trong browser

---

## E. Manual UAT — 5B Experiments (nếu Step B3 đã bật)

| # | Action | Expected | Pass |
|---|--------|----------|------|
| E1 | Tạo experiment (modal) | Draft + variants control/variant_a | [ ] |
| E2 | Transition → running | Status badge cập nhật | [ ] |
| E3 | Thêm manual metric | Bar chart + uplift % | [ ] |
| E4 | Pull GSC (URL có stats) | Observations `source=gsc` | [ ] |
| E5 | Record decision **ship** | Status → completed | [ ] |

---

## F. Soak ≥ 7 ngày (prod)

**Bắt đầu:** ngày apply Step B1 (ghi vào evidence JSON).

Cron (1 lần/ngày):

```bash
# /etc/cron.d/ptt-phase5-soak — ví dụ 06:00 UTC
0 6 * * * root cd /var/www/ptt && ./scripts/phase5_soak_record.sh >> /var/log/ptt-phase5-soak.log 2>&1
```

Daily checklist (DevOps):

| Ngày | `./scripts/phase5_soak_record.sh` ok | Governance blocked spike? | Portal 5xx? | Ghi chú |
|------|--------------------------------------|---------------------------|-------------|---------|
| D+1 | [ ] | [ ] | [ ] | |
| D+2 | [ ] | [ ] | [ ] | |
| D+3 | [ ] | [ ] | [ ] | |
| D+4 | [ ] | [ ] | [ ] | |
| D+5 | [ ] | [ ] | [ ] | |
| D+6 | [ ] | [ ] | [ ] | |
| D+7 | [ ] | [ ] | [ ] | |

Evaluate sau D+7:

```bash
export PHASE5_SKIP_SOAK=0
export PTT_PHASE5_SOAK_DAYS=7
export PTT_PHASE5_SOAK_MIN_SAMPLES=7
./scripts/phase5_prod_cutover_gate.sh
```

- [ ] P5-G04 soak: `span_days ≥ 7`, `sample_count ≥ 7`, `failure_count = 0`
- [ ] Không P1 incident liên quan SEO/AEO Phase 5

Monitor signals:

| Signal | Command |
|--------|---------|
| Governance eval | `SELECT COUNT(*), passed FROM seo_aeo.seo_governance_evaluations WHERE evaluated_at >= NOW()-INTERVAL '24 hours' GROUP BY passed` |
| Flask errors | `journalctl -u ptt --since today \| grep -i governance` |
| Portal bridge | `journalctl -u ptt-crm-api --since today \| grep -i portal.seo` |
| GSC sync | `journalctl -u ptt-seo-gsc-sync -n 20` |

---

## G. Rollback drill (staging hoặc prod maintenance window)

Thực hiện **một lần** trước sign-off:

| # | Action | Verify | Pass |
|---|--------|--------|------|
| G1 | `PTT_SEO_EXPERIMENTS_ENABLED=0` + restart | Experiments UI ẩn, data giữ | [ ] |
| G2 | `PTT_PORTAL_SEO_ENABLED=0` + restart Nest | Portal nav ẩn | [ ] |
| G3 | CRM approve content (không qua portal) | Vẫn hoạt động | [ ] |
| G4 | `PTT_SEO_GOVERNANCE_ENABLED=0` + restart Flask | Publish không bị block | [ ] |
| G5 | Bật lại flags prod plan | Smoke C1/D1 pass | [ ] |

---

## H. Evidence pack (đính kèm ticket / commit)

```bash
cp docs/evidence/phase5-prod-signoff.template.json docs/evidence/phase5-prod-signoff.json
# Điền gates, signoffs, dates
```

| Artifact | Path |
|----------|------|
| Gate report | `.local-dev/phase5-gate-report.json` |
| Portal UAT | `.local-dev/phase5-portal-seo-uat-signoff.json` |
| Soak log | `.local-dev/phase5-soak-evidence.jsonl` |
| Sign-off JSON | `docs/evidence/phase5-prod-signoff.json` |
| PG cutover (prerequisite) | §8 sign-off [`seo-aeo-pg-oauth-uat-cutover.md`](./seo-aeo-pg-oauth-uat-cutover.md) |

---

## I. Final sign-off

- [ ] A — Prerequisites complete
- [ ] B — Staged cutover applied (ghi rõ step đã bật: B1 / B2 / B3)
- [ ] C — Governance UAT pass
- [ ] D — Portal UAT pass (nếu B2)
- [ ] E — Experiments UAT pass (nếu B3)
- [ ] F — Soak ≥ 7 ngày pass
- [ ] G — Rollback drill pass
- [ ] H — Evidence pack attached

**Head of SEO/AEO:** _______________ **Date:** _______________  
**DevOps:** _______________ **Date:** _______________  
**QA:** _______________ **Date:** _______________

---

## Quick commands

```bash
# Gate anytime
./scripts/phase5_prod_cutover_gate.sh

# Soak record
./scripts/phase5_soak_record.sh

# Staged cutover (dry-run)
./scripts/close_phase5_prod_cutover.sh

# Verify SEO PG modules
python3 scripts/verify_seo_aeo_oauth_uat.py --customer-id <PILOT_CUSTOMER_ID>
```

---

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-19 | Initial Phase 5 prod sign-off checklist for VPS |
