# Use Case — Meta Enterprise Ops

> **Prefix:** META · **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Index:** [`README.md`](README.md) · **Spec:** [`SPEC_META_ENTERPRISE_PTTADS.md`](../SPEC_META_ENTERPRISE_PTTADS.md)

---

## META-UC-001 — Kết nối ad account & sync insights

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Tracking/Tech, AM |
| **Priority** | P0 |
| **Trigger** | Onboard Meta service |

**Preconditions:** Meta Business Manager access; system user token configured.

**Main flow:**

1. Map ad account → client ([SVC-UC-008](02-AGENCY-SERVICE-DELIVERY.md)).
2. Worker sync campaigns/adsets/ads T-1 insights.
3. Hub `/meta/facebook-ads` hiển thị spend, impressions, clicks.
4. Sync status green/yellow/red.

**Extensions:**

- **E1 — Token expired:** Alert; re-auth flow.

**Postconditions:** Insights table populated; last_sync timestamp.

**Business rules:** BR-META-01 — Sync T-1 default; intraday optional flag.

**Traceability:** `GET /meta/insights`, `/meta/facebook-ads`

---

## META-UC-002 — Hub map campaign ↔ CRM

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer |
| **Priority** | P0 |

**Main flow:**

1. Unmapped campaigns listed on hub.
2. Buyer select CRM client/project/deal line.
3. Save mapping → CPL calculation enabled.
4. Bulk map CSV optional.

**Postconditions:** `campaign_id` → `client_id` relation stored.

**Traceability:** campaign map UI; map API

---

## META-UC-003 — Xem CPL/ROAS trên hub

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer, AM |
| **Priority** | P0 |

**Main flow:**

1. Hub aggregate spend (Meta) + leads (CRM) + revenue (CRM Won).
2. Display CPL, ROAS, trend 7/30 days.
3. Filter client, campaign, date range.

**Extensions:**

- **E1 — Unmapped spend:** Yellow warning; exclude from client rollup.

**Postconditions:** KPI matches closed-loop spec ([SYS-UC-002](00-SYSTEM-OVERVIEW.md)).

**Traceability:** hub KPI cards; attribution API

---

## META-UC-004 — Webhook lead Meta → CRM

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System |
| **Actor phụ** | CSKH |
| **Priority** | P0 |
| **Trigger** | Meta Leadgen webhook POST |

**Main flow:**

1. [PLAT-UC-004](07-PLATFORM-AUTH-WEBHOOKS.md) verify signature.
2. Parse leadgen payload → normalize fields.
3. Dedup → create/update CRM lead ([CRM-UC-001](01-CRM-CORE.md)).
4. Auto-assign owner.
5. Return 200 OK to Meta.

**Extensions:**

- **E1 — Invalid signature:** 401; alert DevOps.

**Postconditions:** Lead in CRM within SLA <60s.

**Traceability:** `POST /webhooks/meta`, lead ingest worker

---

## META-UC-005 — CAPI event gửi & dedup

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System, Tracking |
| **Priority** | P0 |
| **Trigger** | CRM stage Won / qualified event |

**Main flow:**

1. CRM event hook → CAPI payload builder.
2. Hash PII per Meta spec; event_id dedup.
3. Send Conversions API.
4. Log response; retry on 5xx.

**Postconditions:** Event visible in Meta Events Manager (test mode prod).

**Business rules:** BR-META-02 — event_id = hash(lead_id + event_name + date).

**Traceability:** CAPI service; tracking health UI

---

## META-UC-006 — Tracking health & pixel test

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Tracking/Tech |
| **Priority** | P0 |

**Main flow:**

1. Open tracking health per client.
2. Run pixel/CAPI test event.
3. View match rate, domain verification status.
4. Fix checklist linked.

**Postconditions:** Health score documented pre-launch.

**Traceability:** `/meta/tracking`, test event API

---

## META-UC-007 — Launch Ads wizard

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer |
| **Priority** | P0 |

**Main flow:**

1. `/meta/ads-ops` wizard: objective, budget, audience, creative from hub.
2. Launch QA gate ([SVC-UC-005](02-AGENCY-SERVICE-DELIVERY.md)).
3. Submit → Campaign Write queue ([SVC-UC-007](02-AGENCY-SERVICE-DELIVERY.md)).
4. On approve → Meta create API.

**Postconditions:** Campaign live; Meta ids stored.

**Traceability:** Ads Ops wizard; Meta Marketing API

---

## META-UC-008 — Edit campaign có governance

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer |
| **Priority** | P0 |

**Main flow:** Edit budget/bid/status via same queue; threshold rules for budget increase >X%.

**Postconditions:** Edit audit trail; no direct API bypass in prod.

**Traceability:** campaign write edit jobs

---

## META-UC-009 — Anomaly detection & alert

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System, Buyer |
| **Priority** | P1 |

**Main flow:** Detect spend spike, CPL drift, zero delivery; Slack/email alert; hub banner.

**Traceability:** anomaly rules engine; RPT-M7 alerts

---

## META-UC-010 — Intelligence forecast

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM, Buyer |
| **Priority** | P1 |

**Main flow:** Forecast spend/leads based on historical; scenario budget slider.

**Traceability:** intelligence module; forecast API

---

## META-UC-011 — Breakdown insights (platform/placement)

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer |
| **Priority** | P1 |

**Main flow:** View breakdown by platform, placement, age, gender; export CSV.

**Traceability:** breakdown insights API; hub tabs

---

## META-UC-012 — Pause domain/client spend emergency

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Head, Buyer |
| **Priority** | P0 |
| **Trigger** | Fraud, client request, billing dispute |

**Main flow:**

1. Emergency pause toggle on client/domain.
2. Queue pause all active campaigns via API.
3. Notify AM + client.
4. Audit who triggered.

**Postconditions:** No new spend; campaigns PAUSED on Meta.

**Traceability:** emergency pause API; runbook

---

## META-UC-013 — Weekly client PDF report

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System, AM |
| **Priority** | P1 |

**Main flow:** Scheduler RPT-M3 → aggregate KPI → PDF → email/portal ([SYS-UC-005](00-SYSTEM-OVERVIEW.md)).

**Traceability:** report worker; portal download

---

## META-UC-014 — Horizon migration signoff

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Tech Lead, Buyer |
| **Priority** | P1 |

**Main flow:** Meta API version upgrade checklist; regression test; sign-off doc before deprecation deadline.

**Traceability:** migration runbook; API version config
