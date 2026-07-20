# Runbook — Email deliverability incident

> **Kích hoạt khi:** complaint rate vượt ngưỡng, bounce spike, domain pause, hoặc ESP throttle.  
> **Console:** ops-web `/email/deliverability` (E-11) · **Governance:** `/email/governance`

---

## 1. Triage (15 phút)

1. Mở **Email Hub** (`/email/hub`) — check alerts + client health table.
2. Mở **Deliverability console** — domain SPF/DKIM/DMARC status.
3. Xác định scope: một client / một domain / global.
4. Ghi incident trong audit (`email_mkt.audit_log`).

**Severity:**

| Level | Signal |
|-------|--------|
| P1 | Complaint ≥ 0.3% sends 24h hoặc ESP suspend |
| P2 | Complaint ≥ 0.1% hoặc hard bounce ≥ 2% |
| P3 | DMARC fail / warm-up stall |

---

## 2. Immediate containment

1. **Pause domain sends** — E-11 → [Pause all sends for domain].
2. Nếu campaign đang `sending` → staff cancel/pause campaign (khi worker live).
3. `PTT_EMAIL_SEND_ENABLED=0` (global kill switch) nếu multi-domain spike.

---

## 3. Diagnosis

| Check | Where |
|-------|-------|
| Suppression sync | `/email/suppression` — complaint/unsub auto entries |
| Consent gaps | `/email/consent` — opted_out vs sends |
| Template | Preflight — missing unsubscribe link |
| Audience | Segment compute — stale hoặc import lỗi |
| DNS | Deliverability verify — SPF/DKIM/DMARC |

Query nhanh (PG):

```sql
SELECT event_type, COUNT(*)
FROM email_mkt.engagement_events
WHERE client_id = '<UUID>' AND occurred_at >= NOW() - INTERVAL '24 hours'
GROUP BY event_type;
```

---

## 4. Recovery

1. Fix root cause (template, list hygiene, DNS).
2. Re-verify domain (E-11 Verify DNS).
3. Warm-up: tăng `warm_up_stage` từ từ (manual AM + deliverability lead).
4. Pilot send nhỏ (segment test) trước broadcast.
5. Unpause domain khi metrics 48h ổn định.

---

## 5. Communication

| Audience | Message |
|----------|---------|
| Internal Slack | #email-ops — P-level, client, domain, action |
| Client AM | Tóm tắt + ETA restore |
| Client approver | Pause gửi + lý do (nếu portal campaign pending) |

---

## 6. Post-incident

- [ ] Audit log review (`email_mkt.audit_log`)
- [ ] Update suppression nếu cần
- [ ] Ticket + lesson learned
- [ ] Governance rule tweak (frequency cap) nếu repeat

**Related:** [`email-marketing-prod-pilot-checklist.md`](./email-marketing-prod-pilot-checklist.md)
