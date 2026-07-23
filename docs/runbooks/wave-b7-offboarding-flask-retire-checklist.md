# Wave B7 — Offboarding + Flask retire checklist

> PO: **b7_doc** — checklist vận hành; code B7.1 triển khai ở slice **B7.1-S1** sau khi review spec.  
> Spec: [`2026-07-23-wave-b7-offboarding-flask-retire-design.md`](../specs/2026-07-23-wave-b7-offboarding-flask-retire-design.md)

---

## Trước khi bắt đầu Wave B7

- [ ] `main` có B6-S7 (`feat(wave-b6-s7): Portal MVP production hardening`)
- [ ] Phase 2 prod gate artifact: `.local-dev/phase2-ops-gate-report.json` → `ok: true`
- [ ] Nest + worker + Temporal healthy trên VPS
- [ ] Backup: `pg_dump` + snapshot `.env`

---

## B7.1 — Offboard client (code slice — chưa APPLY prod)

> **Trạng thái:** spec only. Tick khi **B7.1-S1** merged.

- [ ] DDL `client_offboard_audit` applied
- [ ] `POST /api/v1/clients/:id/offboard` + audit GET
- [ ] Revoke all channel tokens + deactivate portal users
- [ ] Emit `ClientOffboarded` + `tenant_locked`
- [ ] ops-web: nút Offboard trên Agency client detail (cap configure)
- [ ] Gate: offboard idempotent + audit row

---

## B7.2 — Portal prod cutover ✅ (B6-S7)

- [ ] `git pull` + rebuild Nest + portal-web trên VPS
- [ ] `psql -f docs/specs/2026-07-23-postgresql-ddl-v3-portal-settings.sql`
- [ ] Env: `PTT_PORTAL_ALLOW_STUB=0`, `PTT_PORTAL_AUTH_MODE=dual`
- [ ] `NEXT_PUBLIC_PTT_API_URL=https://portal.pttads.vn`
- [ ] TLS: `portal.pttads.vn` valid
- [ ] `./scripts/phase3_prod_uat_gate.sh`
- [ ] `python3 -m ptt_crm.phase3_portal_gates` → ok
- [ ] `./scripts/playwright_portal_e2e_temporal.sh` (staging/prod smoke)
- [ ] Human sign-off: `docs/evidence/phase3-uat-signoff.json` (4 roles)

**DoD:** Portal canonical; không còn stub users prod.

---

## B7.3 — Flask readonly soak

PO: **đã soak ≥14 ngày** — một trong hai:

- [ ] **A.** Attach evidence `docs/evidence/flask-readonly-soak.json` (`days` ≥ 14)
- [ ] **B.** Hoặc chạy lại soak:
  ```bash
  # prod .env
  PTT_FLASK_MONOLITH_MODE=readonly
  # monitor 14 ngày → ghi evidence
  ```

- [ ] `./scripts/crm_flask_migration_pack.sh phase5-dry` → PASS

---

## B7.4 — Stop `ptt.service`

- [ ] `./scripts/staging_phase5_gate_pack.sh` → `ok: true`
- [ ] Verify env prod:
  - [ ] `PTT_LEADS_WRITE_SOURCE=pg`
  - [ ] `PTT_WEBHOOKS_FLASK_FALLBACK=0`
  - [ ] `PTT_WEBHOOKS_NEST_META=1`
  - [ ] `PTT_PORTAL_SEO_ENABLED=1`
- [ ] Dry-run:
  ```bash
  set -a && source deploy/env.phase5-flask-retire.example && set +a
  sudo -E ./scripts/close_flask_retirement.sh
  ```
- [ ] Review `.local-dev/phase5-flask-retirement-gate-report.json`
- [ ] **Cutover window — APPLY:**
  ```bash
  sudo -E APPLY=1 ./scripts/close_flask_retirement.sh
  ```
- [ ] `systemctl is-active ptt.service` → **inactive**
- [ ] `PTT_FLASK_MONOLITH_MODE=retired` in `/var/www/ptt/.env`

---

## B7.5 — nginx remove Flask upstream

Included in B7.4 APPLY — verify:

- [ ] `deploy/nginx-rs-flask-retired.conf` active on `rs.pttads.vn`
- [ ] No upstream `:8002` in nginx config
- [ ] POST staff API không 503:
  ```bash
  curl -sf -X POST "https://rs.pttads.vn/api/v1/..." -H "Authorization: Bearer $STAFF_JWT" ...
  ```
- [ ] `curl -I https://rs.pttads.vn/crm/leads` → redirect/200 via ops-web
- [ ] Meta webhook → `job_queue` (no 502)
- [ ] ops-web: `/crm/leads`, `/seo/hub`, `/google/google-ads`
- [ ] portal: `/dashboard`, `/creatives`

---

## Post Wave B7 sign-off

| Role | Sign | Date |
|------|------|------|
| DevOps | [ ] Flask retired verified | |
| AM lead | [ ] Portal UAT | |
| QA | [ ] POST smoke + E2E | |
| PO | [ ] Wave B7 closed | |

Evidence commit (optional):

```bash
cp docs/evidence/phase3-uat-signoff.template.json docs/evidence/phase3-uat-signoff.json
# + flask-retire evidence JSON
```

---

## Rollback nhanh (B7.4/B7.5)

```bash
sudo systemctl enable --now ptt.service
# .env: PTT_FLASK_MONOLITH_MODE=readonly
sudo cp /etc/nginx/sites-available/rs.pttads.vn.pre-phase5.bak /etc/nginx/sites-available/rs.pttads.vn
sudo nginx -t && sudo systemctl reload nginx
```

Chi tiết: [`phase5-flask-retirement-checklist.md`](phase5-flask-retirement-checklist.md)
