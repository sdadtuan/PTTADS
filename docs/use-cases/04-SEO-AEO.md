# Use Case — SEO/AEO Enterprise Ops

> **Prefix:** SEO · **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Index:** [`README.md`](README.md) · **Spec:** [`SPEC_SEO_AEO_OPERATING_SYSTEM.md`](../SPEC_SEO_AEO_OPERATING_SYSTEM.md)

---

## SEO-UC-001 — Onboard client SEO workspace

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | SEO Strategist, AM |
| **Priority** | P0 |
| **Trigger** | HĐ có gói SEO/AEO |

**Preconditions:** Customer active; `PTT_SEO_ENABLED=1`.

**Main flow:**

1. Tạo SEO workspace gắn `client_id`.
2. Nhập primary domain, locale, competitors.
3. Assign strategist owner.
4. Hub `/seo/hub` hiển thị client tile.

**Postconditions:** Workspace ready for OAuth ([SEO-UC-002](#seo-uc-002--oauth-gsc--sync), [SEO-UC-003](#seo-uc-003--oauth-ga4--sync)).

**Traceability:** `/seo/clients/:id`, workspace API; [SYS-UC-001](00-SYSTEM-OVERVIEW.md)

---

## SEO-UC-002 — OAuth GSC & sync

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | SEO Strategist, Tracking |
| **Priority** | P0 |

**Main flow:**

1. Initiate Google Search Console OAuth.
2. Select property matching domain.
3. Worker sync queries, pages, coverage daily.
4. Hub shows sync status + last run.

**Extensions:**

- **E1 — Property mismatch:** Block sync; strategist fix domain verification.

**Postconditions:** GSC data in warehouse; errors surfaced.

**Traceability:** GSC OAuth callback; sync job

---

## SEO-UC-003 — OAuth GA4 & sync

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | SEO Strategist |
| **Priority** | P0 |

**Main flow:** GA4 OAuth → property select → sync sessions, landing pages, conversions for SEO attribution.

**Postconditions:** GA4 linked; combined GSC+GA4 reports available.

**Traceability:** GA4 OAuth; analytics sync worker

---

## SEO-UC-004 — Research → import keywords

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | SEO Strategist |
| **Priority** | P0 |

**Main flow:**

1. Keyword research tool / CSV import.
2. Tag intent, cluster, priority.
3. Assign to content pipeline topics.
4. Track baseline rank ([SEO-UC-011](#seo-uc-011--rank-tracker-capture)).

**Postconditions:** Keyword set versioned per client.

**Traceability:** `/seo/keywords`, import API

---

## SEO-UC-005 — Content pipeline stage advance

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Content Writer, Strategist |
| **Priority** | P0 |

**Main flow:**

1. Create content item: Brief → Draft → Review → Client approval → Scheduled → Published.
2. Advance stage with checklist per transition.
3. Client approval via portal ([PORTAL-UC-007](06-CLIENT-PORTAL.md)).
4. Governance check before publish ([SEO-UC-006](#seo-uc-006--governance-block-publish)).

**Postconditions:** Content audit trail; SLA per stage.

**Traceability:** `/seo/content`, pipeline API

---

## SEO-UC-006 — Governance block publish

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Compliance, System |
| **Priority** | P0 |

**Main flow:**

1. Pre-publish evaluation: thin content, missing meta, banned terms, E-E-A-T flags.
2. **Block** → writer must fix; log evaluation ([SEO-UC-014](#seo-uc-014--clickhouse-bi-export) optional export).
3. **Pass** → allow CMS publish ([SEO-UC-009](#seo-uc-009--cms-publish-webhook)).

**Postconditions:** No publish without pass or admin override.

**Business rules:** BR-SEO-01 — Governance rules configurable per client vertical.

**Traceability:** governance evaluations API; S-14 screen

---

## SEO-UC-007 — Technical audit & issue fix

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | SEO Strategist, Dev client |
| **Priority** | P0 |

**Main flow:** Run crawl audit → issue list (404, canonical, CWV); assign fix; re-crawl verify closed.

**Postconditions:** Issue backlog prioritized P0/P1/P2.

**Traceability:** `/seo/technical`, audit worker

---

## SEO-UC-008 — AEO scan & coverage

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | SEO Strategist |
| **Priority** | P1 |

**Main flow:** Scan AI answer surfaces (SGE, snippets); gap analysis vs competitors; action items in hub.

**Traceability:** AEO module; coverage reports

---

## SEO-UC-009 — CMS publish webhook

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System |
| **Priority** | P1 |
| **Trigger** | Content stage Scheduled → publish time |

**Main flow:** Webhook to client CMS (WordPress/custom); confirm 200; update URL live; trigger freshness ([SEO-UC-010](#seo-uc-010--freshness-queue-refresh)).

**Postconditions:** Published URL stored; sitemap ping optional.

**Traceability:** CMS connector; publish webhook

---

## SEO-UC-010 — Freshness queue refresh

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Strategist |
| **Priority** | P1 |

**Main flow:** Queue stale URLs (>90d); suggest refresh; track before/after metrics.

**Traceability:** freshness queue UI

---

## SEO-UC-011 — Rank tracker capture

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System |
| **Priority** | P1 |

**Main flow:** Daily rank pull for keyword set; delta alerts; chart on client workspace.

**Traceability:** rank tracker job; keyword detail charts

---

## SEO-UC-012 — Executive hub drill-down

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Head, AM |
| **Priority** | P0 |

**Main flow:** `/seo/hub` client health → click client → issues/content/rank ([SYS-UC-007](00-SYSTEM-OVERVIEW.md) ≤3 clicks).

**Postconditions:** PO spec F5 satisfied.

**Traceability:** SEO UI spec §4.5; hub E2E

---

## SEO-UC-013 — Client PDF report export

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Strategist, AM |
| **Priority** | P0 |

**Main flow:** Select period → generate PDF (traffic, ranks, content delivered) → portal/email ([SYS-UC-005](00-SYSTEM-OVERVIEW.md)).

**Traceability:** `/seo/reports`, PDF worker

---

## SEO-UC-014 — ClickHouse BI export

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Data team |
| **Priority** | P1 |

**Main flow:** Export SEO events to ClickHouse; Grafana dashboards; BI status endpoint.

**Traceability:** ClickHouse pipeline; Grafana links
