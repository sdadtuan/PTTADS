# Chi tiết hành động — SEO/AEO (SEO)

> **UC gốc:** [`../04-SEO-AEO.md`](../04-SEO-AEO.md)  
> **Cross-system:** [`00-SYSTEM-ACTIONS.md`](00-SYSTEM-ACTIONS.md) · [`06-PORTAL-ACTIONS.md`](06-PORTAL-ACTIONS.md)

---

## SEO-UC-001 — Onboard client SEO workspace

**Mục tiêu khách hàng:** *"Client SEO có workspace riêng — domain, competitor, link CRM."*

**Actors:** SEO Strategist, AM

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/seo/clients` | **+ Client** hoặc open tile | domain, locale | Workspace id | ✓ |
| 2 | Strategist | `/seo/clients/[id]` | Save config | competitors, market, goals | Saved | ✓ |
| 3 | Strategist | Same | Set primary domain + sitemap URL | URL | Validated | ✓ |
| 4 | AM | Same | Link **customer_id** ↔ workspace | CRM id | Cross-ref | ✓ |
| 5 | Strategist | `/seo/hub` | Verify client appears | health score | Row visible | ✓ |
| 6 | AM | [`00-SYSTEM-ACTIONS.md`](00-SYSTEM-ACTIONS.md#sys-uc-001--onboard-client-mới-end-to-end) | SEO branch onboard nếu HĐ SEO | — | Checklist tick | ✓ |
| 7 | Strategist | `/seo/clients/[id]` | Kickoff GSC connect | — | → [UC-002](#seo-uc-002--oauth-gsc--sync) | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Workspace domain unique
- [ ] Hub health score calculable

---

## SEO-UC-002 — OAuth GSC & sync

**Mục tiêu khách hàng:** *"Google Search Console data sync T-1 — clicks, impressions, queries."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/seo/clients/[id]` | **Connect GSC** OAuth | Google account | Redirect | ✓ |
| 2 | Strategist | OAuth callback | Select **property** | domain match | Property linked | ✓ |
| 3 | Strategist | Same | **Run GSC sync** | — | Job queued | ✓ |
| 4 | System | worker | Pull queries + pages T-1 | property id | Rows stored | ✓ |
| 5 | Strategist | `/seo/hub` | Check sync banner **green** | — | Last sync time | ✓ |
| 6 | Strategist | `/seo/reports` | Preview GSC data | T-7 | Chart load | ✓ |
| 7 | Strategist | Same | Verify domain mismatch alert | — | None | ✓ |

#### Nhánh E1 — OAuth revoked
Banner red → re-connect bước 1.

#### Tiêu chí nghiệm thu
- [ ] GSC sync ≤ 24h lag
- [ ] Property domain matches workspace

---

## SEO-UC-003 — OAuth GA4 & sync

**Mục tiêu khách hàng:** *"GA4 organic traffic sync — báo cáo kết hợp GSC + GA4."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/seo/clients/[id]` | **Connect GA4** OAuth | Google account | Redirect | ✓ |
| 2 | Strategist | Callback | Select **property** + data stream | property id | Linked | ✓ |
| 3 | Strategist | Same | **Run GA4 sync** | — | Job ok | ✓ |
| 4 | System | worker | Pull sessions, conversions T-1 | — | Rows stored | ✓ |
| 5 | Strategist | `/seo/reports` | Combined **GSC + GA4** view | T-7 | Chart | ✓ |
| 6 | Strategist | `/seo/hub` | Verify both GSC + GA4 green | — | Badges | ✓ |

#### Tiêu chí nghiệm thu
- [ ] GA4 organic segment visible in reports
- [ ] Combined report loads ≤ 5s

---

## SEO-UC-004 — Research → import keywords

**Mục tiêu khách hàng:** *"Keyword list có intent, cluster, priority — gắn content pipeline."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/seo/research` | Run research hoặc **Import CSV** | keywords file | Preview | ✓ |
| 2 | Strategist | Same | Map columns: keyword, volume, difficulty | mapper | Validated | ✓ |
| 3 | Strategist | Row edit | Tag **intent**, cluster, priority | tags | Saved | ✓ |
| 4 | Strategist | Same | Assign keyword → content topic | topic id | Linked | ✓ |
| 5 | Strategist | `/seo/content` | **+ Content** from keyword | brief auto | Content id | ✓ [UC-005](#seo-uc-005--content-pipeline-stage-advance) |
| 6 | Strategist | `/seo/ranks` | Add to rank tracker list | — | Tracking | ○ |

#### Tiêu chí nghiệm thu
- [ ] Import dedup same keyword+client
- [ ] Priority P0 keywords have content assigned

---

## SEO-UC-005 — Content pipeline stage advance

**Mục tiêu khách hàng:** *"Content từ brief → draft → duyệt khách → publish có governance."*

**Actors:** Writer, Lead, Client Approver, Strategist

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Writer | `/seo/content` | **+ Content** Brief | title, keyword | Draft id | ✓ |
| 2 | Writer | `/seo/content/[id]` | Write body → **Save** | HTML/MD | Version saved | ✓ |
| 3 | Lead | Same | Advance → **Internal review** | — | Stage update | ✓ |
| 4 | Lead | Same | **Approve internal** | comment | → client_review | ✓ |
| 5 | Strategist | Same | **Submit client approval** | — | pending_client | ✓ |
| 6 | Client | portal `/seo/content/[id]` | **Approve** / **Reject** | comment if reject | Decision | ✓ [PORTAL-UC-007](06-PORTAL-ACTIONS.md) |
| 7 | Strategist | ops content detail | Advance → **Scheduled** | publish date | Scheduled | ✓ |
| 8 | System | [UC-006](#seo-uc-006--governance-block-publish) | Pre-publish eval pass | — | Publish allowed | ✓ |

#### Nhánh E1 — Client reject
Bước 6 reject → Writer revise bước 2 → resubmit bước 5.

#### Tiêu chí nghiệm thu
- [ ] Reject requires comment on portal
- [ ] Publish blocked if governance fail

---

## SEO-UC-006 — Governance block publish

**Mục tiêu khách hàng:** *"Content không publish nếu vi phạm rule compliance — E-E-A-T, banned terms."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Compliance | `/seo/governance` | Configure rules | banned words, min words | Rules saved | ✓ |
| 2 | System | Pre-publish eval | Run rules on content | content id | pass/fail | ✓ |
| 3 | Writer | `/seo/content/[id]` | View **blocked** reasons | — | Fix list | ✓ if fail |
| 4 | Writer | Same | Fix content → **Save** | edits | Re-eval queued | ✓ |
| 5 | System | — | Re-eval → **pass** | — | Green | ✓ |
| 6 | Strategist | Same | **Publish** action | — | Live/scheduled | ✓ pass only |
| 7 | Compliance | `/seo/governance` | Review eval history | filter | Audit | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Fail blocks publish button
- [ ] Eval history immutable

---

## SEO-UC-007 — Technical audit & issue fix

**Mục tiêu khách hàng:** *"Technical SEO issues tracked — P0 fix trước content scale."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/seo/technical` | Run / view audit | crawl config | Issue list | ✓ |
| 2 | Strategist | Same | Filter **P0** severity | — | Critical list | ✓ |
| 3 | Strategist | Issue row | Assign dev/client owner | staff/contact | Assigned | ✓ |
| 4 | Dev client | Site CMS | Fix on production | — | Deploy | ✓ external |
| 5 | Strategist | Same | **Re-crawl** verify | — | Issue closed | ✓ |
| 6 | Strategist | `/seo/hub` | Health score improves | — | Score up | ○ |
| 7 | AM | Client report | Include P0 status | — | Comms | ○ |

#### Tiêu chí nghiệm thu
- [ ] P0 issues have owner + target date
- [ ] Re-crawl closes issue with evidence

---

## SEO-UC-008 — AEO scan & coverage

**Mục tiêu khách hàng:** *"Biết gap AI Overview / answer engines vs competitors."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/seo/aeo` | **+ Query** set | queries list | Saved | ✓ |
| 2 | Strategist | Same | **Run scan** | — | Gap report | ✓ |
| 3 | Strategist | Same | Compare vs competitors | domains | Coverage % | ✓ |
| 4 | Strategist | Action items | Push gaps → content pipeline | topics | Linked | ✓ [UC-005](#seo-uc-005--content-pipeline-stage-advance) |
| 5 | Strategist | `/seo/reports` | Include AEO section | period | Export | ○ |

#### Tiêu chí nghiệm thu
- [ ] Scan completes ≤ 30 min per client

---

## SEO-UC-009 — CMS publish webhook

**Mục tiêu khách hàng:** *"Content scheduled publish tự động lên CMS client."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/seo/cms` | Save **publish target** URL + auth | webhook config | Saved | ✓ |
| 2 | Strategist | `/seo/content/[id]` | Schedule publish datetime | — | Queued | ✓ |
| 3 | System | Scheduler | POST webhook CMS | payload | 200 OK | ✓ |
| 4 | Strategist | Content detail | Verify **URL live** field | URL | HTTP 200 | ✓ |
| 5 | Strategist | `/seo/freshness` | URL enters freshness queue | — | Tracked | ○ |

#### Tiêu chí nghiệm thu
- [ ] Webhook failure retries + alert

---

## SEO-UC-010 — Freshness queue refresh

**Mục tiêu khách hàng:** *"Content stale được refresh — rankings không tụt do outdated."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/seo/freshness` | View **stale URLs** | threshold days | List | ✓ |
| 2 | Strategist | Row | Assign writer refresh | staff | Task | ✓ |
| 3 | Writer | `/seo/content/[id]` | Update content → publish | — | New version | ✓ |
| 4 | Strategist | `/seo/ranks` | Compare metrics before/after | T+30 | Delta | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Stale URLs flagged per policy (e.g. >180d)

---

## SEO-UC-011 — Rank tracker capture

**Mục tiêu khách hàng:** *"Theo dõi ranking keyword hàng ngày — delta chart cho client."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | Daily job | Capture ranks SERP | keyword list | Rows | ✓ |
| 2 | Strategist | `/seo/ranks` | View **delta chart** | T-30 | Chart | ✓ |
| 3 | Strategist | Same | Drill keyword detail | keyword | History | ✓ |
| 4 | Strategist | Same | **Import CSV** manual backup | file | Merged | ○ |
| 5 | Client | portal `/seo` | View summary widget | — | Read-only | ✓ [PORTAL-UC-004](06-PORTAL-ACTIONS.md) |

#### Tiêu chí nghiệm thu
- [ ] Daily capture ≥ 95% keywords

---

## SEO-UC-012 — Executive hub drill-down

**Mục tiêu khách hàng:** *"Head drill client SEO health ≤3 clicks — actionable issues."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Head | `/seo/hub` | Filter customer/market | filters | Table | ✓ click 1 |
| 2 | Head | Client row click | → `/seo/clients/[id]` | — | Workspace | ✓ click 2 |
| 3 | Head | Tab **issues** hoặc **content** | Drill item | — | Actionable | ✓ click 3 |
| 4 | Head | Issue/content detail | Assign or approve action | — | Done | ✓ |
| 5 | Head | — | Total clicks ≤ 3 to actionable | — | [SYS-UC-007](00-SYSTEM-ACTIONS.md) | ✓ |

#### Tiêu chí nghiệm thu
- [ ] ≤3 clicks hub → actionable record

---

## SEO-UC-013 — Client PDF report export

**Mục tiêu khách hàng:** *"Khách nhận báo cáo SEO monthly — GSC + content + technical summary."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/seo/reports` | Select client + period | month | Preview | ✓ |
| 2 | Strategist | Same | Verify GSC+GA4 sync green | — | Data sane | ✓ |
| 3 | Strategist | Same | **Export PDF** | — | File download | ✓ |
| 4 | AM | Email | Deliver to client | attachment | Sent | ○ |
| 5 | Client | portal `/seo/reports` | View/download self-serve | period | PDF | ✓ |
| 6 | Client | portal `/seo` | Dashboard widgets match report | — | Consistent | ✓ |

#### Tiêu chí nghiệm thu
- [ ] PDF matches on-screen report ± rounding
- [ ] Portal export scoped tenant

---

## SEO-UC-014 — ClickHouse BI export

**Mục tiêu khách hàng:** *"Data team export SEO BI — Grafana staff; portal PDF fallback."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Data | `/seo/bi` | Run export job | date range | File/link | ✓ staff |
| 2 | Data | Same | Open **Grafana** embed link | — | Dashboard | ✓ |
| 3 | Client | portal | ⚠ No Grafana embed | — | PDF only | ⚠ GAP-P1-03 |
| 4 | AM | `/seo/reports` | Provide PDF alternative | — | Client OK | ○ |

#### Tiêu chí nghiệm thu
- [ ] Staff Grafana link authenticated
- [ ] Export reproducible same period

---

## Luồng SEO end-to-end

| # | UC | Mục tiêu |
|---|-----|----------|
| 1 | SEO-001 | Workspace |
| 2 | SEO-002/003 | GSC + GA4 sync |
| 3 | SEO-004 | Keywords |
| 4 | SEO-005/006 | Content + governance |
| 5 | SEO-013 | Client report |

**Liên kết SYS:** [SYS-UC-004](00-SYSTEM-ACTIONS.md) SEO approval inbox.
