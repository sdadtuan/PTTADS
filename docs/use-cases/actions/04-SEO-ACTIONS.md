# Chi tiết hành động — SEO/AEO (SEO)

> **UC gốc:** [`../04-SEO-AEO.md`](../04-SEO-AEO.md)

---

## SEO-UC-001 — Onboard client SEO workspace

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Strategist | `/seo/clients` | Open / create client tile | domain, locale | ✓ |
| 2 | Strategist | `/seo/clients/[id]` | Save config | competitors, market | ✓ |
| 3 | Strategist | `/seo/hub` | Verify client appears | health score | ✓ |
| 4 | AM | Link CRM | customer_id ↔ workspace | ✓ |

---

## SEO-UC-002 — OAuth GSC & sync

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Strategist | `/seo/clients/[id]` | **Connect GSC** OAuth | ✓ redirect Google |
| 2 | Strategist | OAuth callback | Select property | ✓ domain match |
| 3 | Strategist | Same | **Run GSC sync** | ✓ job ok |
| 4 | Strategist | `/seo/hub` | Check sync banner green | ✓ |

---

## SEO-UC-003 — OAuth GA4 & sync

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Strategist | `/seo/clients/[id]` | **Connect GA4** | ✓ |
| 2 | Strategist | Run GA4 sync | — | ✓ |
| 3 | Strategist | `/seo/reports` | Combined GSC+GA4 | ✓ |

---

## SEO-UC-004 — Research → import keywords

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Strategist | `/seo/research` | Research or **Import CSV** | keywords | ✓ |
| 2 | Strategist | Row edit | Tag intent, cluster, priority | ✓ |
| 3 | Strategist | Assign to content | link topic | ✓ |

---

## SEO-UC-005 — Content pipeline stage advance

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Writer | `/seo/content` | **+ Content** Brief | ✓ |
| 2 | Writer | `/seo/content/[id]` | Draft body → Save | ✓ |
| 3 | Lead | Same | Advance → Internal review | ✓ |
| 4 | Lead | Approve internal | → **client_review** | ✓ |
| 5 | Client | portal `/seo/content/[id]` | Approve/Reject | ✓ |
| 6 | Strategist | ops content detail | Advance → Scheduled | ✓ governance |

---

## SEO-UC-006 — Governance block publish

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | System | Pre-publish eval | Run rules | ✓ pass/fail |
| 2 | Compliance | `/seo/governance` | Configure rules | ✓ |
| 3 | Writer | `/seo/content/[id]` | Fix if **blocked** | ✓ re-eval pass |
| 4 | Strategist | Publish action | Only if pass | ✓ |

---

## SEO-UC-007 — Technical audit & issue fix

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Strategist | `/seo/technical` | Run/view audit issues | ✓ |
| 2 | Strategist | Filter P0 | Assign dev client | ✓ |
| 3 | Dev client | Fix on site | — | ✓ |
| 4 | Strategist | Re-crawl | Close issue | ✓ |

---

## SEO-UC-008 — AEO scan & coverage

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Strategist | `/seo/aeo` | **+ Query** | ✓ |
| 2 | Strategist | Run scan | gap vs competitors | ✓ |
| 3 | Strategist | Action items → content pipeline | ✓ |

---

## SEO-UC-009 — CMS publish webhook

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Strategist | `/seo/cms` | Save publish target URL | ✓ |
| 2 | System | Scheduled publish | Webhook POST CMS | ✓ 200 |
| 3 | Strategist | Content detail | URL live field | ✓ |

---

## SEO-UC-010 — Freshness queue refresh

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Strategist | `/seo/freshness` | View stale URLs | ✓ |
| 2 | Writer | Assign refresh | update content | ✓ |
| 3 | Strategist | Compare metrics before/after | ✓ |

---

## SEO-UC-011 — Rank tracker capture

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | System | Daily job | Capture ranks | ✓ |
| 2 | Strategist | `/seo/ranks` | View delta chart | ✓ |
| 3 | Strategist | Import CSV manual | ○ |

---

## SEO-UC-012 — Executive hub drill-down

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Head | `/seo/hub` | Filter customer/market | ✓ click 1 |
| 2 | Head | Client row → `/seo/clients/[id]` | ✓ click 2 |
| 3 | Head | Tab issues/content | ✓ click 3 |

---

## SEO-UC-013 — Client PDF report export

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Strategist | `/seo/reports` | Select period → **Export** | ✓ |
| 2 | Client | portal `/seo/reports` | View/download | ✓ |

---

## SEO-UC-014 — ClickHouse BI export

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Data | `/seo/bi` | Export + Grafana link | ✓ staff |
| 2 | Client | portal | ⚠ GAP-P1-03 no embed | ⚠ PDF only |
