# Email Marketing — Production pilot checklist (Gate A / EM-5)

> **Mục tiêu:** Pilot 1–2 client trên ops-web + Nest + portal với soak ≥ 7 ngày trước mở rộng.  
> **Env mẫu:** [`deploy/env.em5-prod.example`](../../deploy/env.em5-prod.example) · real send: [`deploy/env.em5-prod-send.example`](../../deploy/env.em5-prod-send.example)  
> **Gate tự động:** `./scripts/phase5_email_prod_pilot_gate.sh`

---

## Participants

| Role | Name | Sign-off |
|------|------|----------|
| Head Email / CoE | | [ ] |
| Compliance | | [ ] |
| AM (pilot client) | | [ ] |
| Client approver (portal) | | [ ] |
| DevOps | | [ ] |

---

## A. Prerequisites

### A1. Infrastructure

- [ ] PostgreSQL `email_mkt.*` schema applied (EM-0 → EM-3 + EM-11 journey enrollments)
- [ ] Nest `ptt-crm-api` + ops-web + portal-web healthy
- [ ] Staff RBAC caps `crm_email_mkt_*` seeded: `python3 scripts/seed_staff_email_mkt_permissions.py`
- [ ] `DATABASE_URL` trỏ PG prod/staging (không SQLite)
- [ ] Backup `pg_dump` trước change window

### A2. Pilot identifiers

| Biến | Giá trị |
|------|---------|
| `PILOT_CLIENT_UUID` | __________ |
| Workspace name | __________ |
| Sending domain | __________ |
| Portal approver email | __________ |

### A3. Automated gates (local/staging mirror)

```bash
cd /path/to/PTTADS
export DATABASE_URL=postgresql://...
export OPS_E2E_API_URL=http://127.0.0.1:3000
chmod +x scripts/phase9_email_wave4_gate.sh
./scripts/phase9_email_wave4_gate.sh --refresh-wave
```

- [ ] `.local-dev/phase9-email-wave4-report.json` → `"ok": true`
- [ ] `.local-dev/phase5-email-pilot-gate-report.json` → `"ok": true`
- [ ] EM-0..EM-4 + EM-6..EM-8b reports trong `.local-dev/` đều `"ok": true`
- [ ] Pytest email (Nest + phase5 + wave4) pass

**Full regression (optional CI):**

```bash
./scripts/email_mkt_full_regression_gate.sh
```

---

## B. Staged cutover (prod)

> Thứ tự: **Ops admin (EM-1)** → **Send MVP (EM-2)** → **Enterprise (EM-3)** → **Portal (EM-4)**.  
> Không bật portal + journeys cùng lúc lần đầu.

### B1. Step 1 — Ops admin only

```bash
PTT_EMAIL_ENABLED=1
PTT_EMAIL_SEND_ENABLED=0
PTT_EMAIL_JOURNEYS_ENABLED=0
PTT_EMAIL_PORTAL_ENABLED=0
```

Verify: `/email/hub`, clients, contacts, consent, suppression.

### B2. Step 2 — Send MVP

```bash
PTT_EMAIL_SEND_ENABLED=1
```

Verify: segment → template preflight → campaign submit → `pending_approval`.

### B3. Step 3 — Enterprise depth

```bash
PTT_EMAIL_JOURNEYS_ENABLED=1   # optional pilot
```

Verify: deliverability console, reports KPI.

### B4. Step 4 — Client portal

```bash
PTT_EMAIL_PORTAL_ENABLED=1
```

Verify: portal `/email`, `/email/approvals`, approver approve flow.

### B5. Step 5 — Real ESP send (prod pilot)

Copy [`deploy/env.em5-prod-send.example`](../../deploy/env.em5-prod-send.example) → VPS `.env`:

```bash
PTT_EMAIL_ESP_DRY_RUN=0
EMAIL_ESP_PROVIDER=sendgrid
SENDGRID_API_KEY=SG....
SENDGRID_WEBHOOK_VERIFICATION_KEY=...
EM5_EXPECT_ESP_DRY_RUN=0
```

Verify: approved campaign → `send_queue` → ESP message ID (not `dry-*`).

Enable systemd timers on VPS:

```bash
sudo cp deploy/ptt-email-campaign-schedule.* deploy/ptt-email-soak.* /etc/systemd/system/
sudo cp scripts/email_campaign_schedule_due_cron.sh /var/www/ptt/scripts/
sudo systemctl daemon-reload
sudo systemctl enable --now ptt-email-campaign-schedule.timer
sudo systemctl enable --now ptt-email-soak.timer
# When journeys enabled:
# sudo cp deploy/ptt-email-journey.* /etc/systemd/system/
# sudo cp scripts/email_journey_cron.sh /var/www/ptt/scripts/
# sudo systemctl enable --now ptt-email-journey.timer
```

---

## C. Soak ≥ 7 ngày

Cron daily (staging/prod):

```bash
./scripts/phase5_email_soak_record.sh
```

Evaluate:

```bash
export EM5_SKIP_SOAK=0
export PTT_EM5_SOAK_DAYS=7
python3 -m ptt_crm.phase5_email_soak_evidence evaluate
```

- [ ] `span_days` ≥ 7, `failure_count` = 0
- [ ] Không complaint spike không giải thích (xem runbook deliverability)

---

## D. Manual UAT

- [ ] Staff: import contact + consent `opted_in`
- [ ] Staff: campaign preflight pass + submit
- [ ] Portal approver: preview email + approve → status `approved` (Wave 4 send orchestration)
- [ ] Public: preferences / unsubscribe token flow
- [ ] Deliverability: register domain + verify DNS (simulated hoặc thật)
- [ ] Governance: global rules visible (E-13)

---

## E. Sign-off

1. Copy template → `.local-dev/em5-email-pilot-signoff.json`
2. Điền pilot IDs, flags, manual UAT, signoffs
3. Re-run gate với `EM5_REQUIRE_SIGNOFF=1` (optional)

```bash
cp docs/evidence/em5-email-pilot-signoff.template.json .local-dev/em5-email-pilot-signoff.json
# edit signoffs...
EM5_REQUIRE_SIGNOFF=1 ./scripts/phase5_email_prod_pilot_gate.sh
```

---

## Rollback

| Step | Action |
|------|--------|
| Portal issue | `PTT_EMAIL_PORTAL_ENABLED=0`, restart Nest |
| Send issue | `PTT_EMAIL_SEND_ENABLED=0`, pause domains (E-11) |
| Full rollback | `PTT_EMAIL_ENABLED=0`, ops-web ẩn nav (flag) |

Incident: [`email-deliverability-incident.md`](./email-deliverability-incident.md)
