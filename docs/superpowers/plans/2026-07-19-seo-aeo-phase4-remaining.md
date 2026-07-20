# Phase 4 Remaining — AEO v2 → Freshness → Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hoàn thiện Phase 4 SEO/AEO Enterprise OS — unified AEO Console (migrate legacy), Content Freshness scoring + refresh queue, Authority & Trust console — tất cả **PostgreSQL-only** cho DDL mới.

**Architecture:** Ba sub-phase độc lập, mỗi phase ship được riêng. AEO v2 wrap `crm_aeo.py` qua `ptt_seo/aeo.py`, dual-write scan results → `seo_ai_mentions` PG. Freshness đọc GSC/GA4 + content metadata → decay score → auto `refresh_required`. Authority import CSV backlinks/citations → `seo_authority_signals`. Job queue pattern giống `seo_gsc_sync`.

**Tech Stack:** Flask 3, PostgreSQL `seo_aeo.*`, SQLite CRM bridge, Anthropic SDK, `ptt_jobs` queue, systemd timers, vanilla JS + agency design tokens.

**Prerequisites (blocker):**
- Phase 3.5 production cutover: `SEO_AEO_DB=pg`, backfill chạy xong
- GSC/GA4 OAuth đã UAT (data trong `seo_gsc_daily_stats`, `seo_ga4_daily_stats`)
- `PTT_JOBS_ENABLED=1` hoặc `PTT_JOBS_SYNC_FALLBACK=1` trên worker

**Refs:**
- Master: [`docs/SPEC_SEO_AEO_OPERATING_SYSTEM.md`](../SPEC_SEO_AEO_OPERATING_SYSTEM.md) §9 Phase 4
- UI: [`docs/SPEC_UI_UX_SEO_AEO.md`](../SPEC_UI_UX_SEO_AEO.md) S-10, S-11
- Architecture: [`docs/specs/2026-07-19-seo-aeo-architecture.md`](../specs/2026-07-19-seo-aeo-architecture.md) §6.3, §7.5, §8.1
- PG policy: [`docs/specs/2026-07-19-seo-aeo-pg-cutover-policy.md`](../specs/2026-07-19-seo-aeo-pg-cutover-policy.md)
- Legacy AEO: `crm_aeo.py`, `templates/crm_aeo.html`

## Global Constraints

- **Storage:** Mọi bảng mới → `deploy/sql/seo_aeo_pg_schema.sql` + `ptt_seo/pg_schema.py` (apply via `ensure_pg_schema`). **Không** thêm SQLite DDL mới (policy ADR-SEO-006).
- **OAuth/integrations:** PG-only via `seo_pg_only()` / `integrations_json`.
- **RBAC:** Section `crm_seo_aeo` (view/edit/create/configure). Granular keys deferred — dùng `_can("view")` / `_can("edit")` như blueprint hiện tại.
- **Routes:** Prefix `/api/v1/seo`, pages `/crm/seo/*`.
- **Job naming:** Underscore convention: `seo_aeo_scan`, `seo_freshness_scan` (không dùng `seo.scan.aeo` dot notation trong code).
- **UI copy:** Tiếng Việt labels, empty states, errors (SPEC_UI_UX §8).
- **Service slugs:** `dich-vu-aeo`, `dich-vu-seo-tong-the`, `dich-vu-seo-local`, `dich-vu-seo-audit`.
- **Tests:** `python3 -m pytest tests/test_seo_aeo_phase4_*.py -v` — TDD per task.
- **Commits:** Chỉ khi user yêu cầu; mỗi task = 1 logical commit nếu được yêu cầu commit.

---

## Timeline Overview

| Sub-phase | Scope | Effort | Ship criteria |
|-----------|-------|--------|---------------|
| **4A** | AEO Console v2 + PG mentions | ~2 tuần | S-10 live, legacy redirect, batch scan job |
| **4B** | Content Freshness | ~1 tuần | Decay scores, refresh queue, weekly timer |
| **4C** | Authority Console | ~1 tuần | S-11 live, CSV import, hub metrics |

**Total:** ~4 tuần (sau PG cutover production).

---

# Sub-phase 4A — AEO Console v2

> Migrate Phase 0 `/crm/aeo` → unified `/crm/seo/aeo` (S-10). Scan results persist vào PG `seo_ai_mentions`. Legacy routes giữ backward compat 6 tháng.

## File map (4A)

| File | Action | Responsibility |
|------|--------|----------------|
| `deploy/sql/seo_aeo_pg_schema.sql` | Modify | `seo_ai_mentions`, `seo_aeo_scan_runs` |
| `ptt_seo/aeo.py` | Create | Facade: queries, scan, coverage, batch enqueue |
| `ptt_seo/connectors/aeo_scan.py` | Create | Anthropic scan + write mentions PG |
| `ptt_jobs/handlers/seo_aeo_scan.py` | Create | Job handler |
| `ptt_worker/__main__.py` | Modify | Dispatch `seo_aeo_scan` |
| `blueprints/seo_aeo.py` | Modify | AEO page + 6 API routes |
| `templates/crm_seo_aeo_console.html` | Create | S-10 UI |
| `static/crm_seo_aeo_console.js` | Create | Client-side |
| `scripts/migrate_crm_aeo_to_pg.py` | Create | One-way backfill queries → seo_questions + mentions |
| `tests/test_seo_aeo_phase4_aeo_v2.py` | Create | Unit + stub scan tests |

### Task 4A-1: PG schema — `seo_ai_mentions` + scan runs

**Files:**
- Modify: `deploy/sql/seo_aeo_pg_schema.sql` (append before `seo_alerts`)
- Modify: `scripts/migrate_sqlite_seo_aeo_to_pg.py` (add table if backfill needed)

**Interfaces:**
- Produces: tables `seo_aeo.seo_ai_mentions`, `seo_aeo.seo_aeo_scan_runs`

**DDL to append:**

```sql
CREATE TABLE IF NOT EXISTS seo_aeo.seo_ai_mentions (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    question_id     INTEGER,
    platform        TEXT NOT NULL DEFAULT 'anthropic_sim',
    query_text      TEXT NOT NULL DEFAULT '',
    source_url      TEXT NOT NULL DEFAULT '',
    citation_status TEXT NOT NULL DEFAULT 'absent',
    brand_visible   BOOLEAN NOT NULL DEFAULT FALSE,
    gap_notes       TEXT NOT NULL DEFAULT '',
    ai_response     TEXT NOT NULL DEFAULT '',
    legacy_scan_id  INTEGER,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_ai_mentions_customer ON seo_aeo.seo_ai_mentions (customer_id, detected_at DESC);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_aeo_scan_runs (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    queries_total   INTEGER NOT NULL DEFAULT 0,
    queries_done    INTEGER NOT NULL DEFAULT 0,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    error_message   TEXT NOT NULL DEFAULT ''
);
```

- [ ] **Step 1:** Append DDL to `seo_aeo_pg_schema.sql`
- [ ] **Step 2:** Run locally: `python3 -c "from ptt_jobs.db import pg_connection; from ptt_seo.pg_schema import ensure_pg_schema; c=pg_connection().__enter__(); ensure_pg_schema(c)"` (skip if no PG — document in task notes)
- [ ] **Step 3:** Verify table exists via `\dt seo_aeo.*` or information_schema query

---

### Task 4A-2: `ptt_seo/aeo.py` — facade over legacy + PG mentions

**Files:**
- Create: `ptt_seo/aeo.py`
- Test: `tests/test_seo_aeo_phase4_aeo_v2.py`

**Interfaces:**
- Consumes: `crm_aeo.list_queries`, `crm_aeo.run_scan`, `crm_aeo.generate_content`, `crm_connection()`, `seo_pg_only()`
- Produces:

```python
def list_aeo_queries(customer_id: int) -> list[dict[str, Any]]: ...
def aeo_coverage_summary(customer_id: int) -> dict[str, Any]:
    """Returns {total, visible, coverage_pct, readiness_avg, last_scan_at}."""
def list_mention_trends(customer_id: int, *, days: int = 90) -> list[dict[str, Any]]: ...
def link_query_to_seo_question(customer_id: int, query_id: int) -> int | None: ...
```

**Coverage formula:** `coverage_pct = visible / total * 100` (giống hub hiện tại).

- [ ] **Step 1: Write failing test**

```python
def test_aeo_coverage_empty():
    from ptt_seo.aeo import aeo_coverage_summary
    with patch("ptt_seo.aeo._list_legacy_queries", return_value=[]):
        out = aeo_coverage_summary(1)
    assert out["total"] == 0
    assert out["coverage_pct"] == 0.0
```

- [ ] **Step 2:** Run `pytest tests/test_seo_aeo_phase4_aeo_v2.py::test_aeo_coverage_empty -v` → FAIL
- [ ] **Step 3:** Implement `ptt_seo/aeo.py` — delegate query list to `crm_aeo` via `crm_connection()`
- [ ] **Step 4:** Run test → PASS
- [ ] **Step 5:** Add test `test_aeo_coverage_with_visible_queries` (2 queries, 1 visible → 50%)

---

### Task 4A-3: `aeo_scan.py` — scan + dual-write PG mention

**Files:**
- Create: `ptt_seo/connectors/aeo_scan.py`
- Test: `tests/test_seo_aeo_phase4_aeo_v2.py`

**Interfaces:**
- Consumes: `crm_aeo.run_scan`, `seo_pg_only()`
- Produces:

```python
def aeo_stub_mode() -> bool:
    """PTT_AEO_SCAN_STUB=1"""

def scan_query(customer_id: int, query_id: int) -> dict[str, Any]:
    """Run legacy scan + insert seo_ai_mentions row. Returns {ok, mention_id, brand_visible}."""

def scan_customer_batch(customer_id: int, *, query_ids: list[int] | None = None) -> dict[str, Any]:
    """Scan all (or subset) queries for customer."""
```

**Stub mode:** When `PTT_AEO_SCAN_STUB=1`, skip Anthropic call; insert fake mention with `brand_visible=True`.

- [ ] **Step 1:** Test stub scan writes PG row (mock `seo_pg_only` + in-memory SQLite for CRM)
- [ ] **Step 2:** Implement `scan_query` — after `crm_aeo.run_scan`, read latest scan from CRM, INSERT into `seo_ai_mentions`
- [ ] **Step 3:** Map `citation_status`: `cited` if brand_visible and gap empty, `mentioned` if visible, else `absent`
- [ ] **Step 4:** Test batch scan counts

---

### Task 4A-4: Job handler `seo_aeo_scan`

**Files:**
- Create: `ptt_jobs/handlers/seo_aeo_scan.py`
- Modify: `ptt_worker/__main__.py`
- Modify: `ptt_seo/aeo.py` — add `enqueue_aeo_scan(customer_id, query_ids=None)`

**Payload:**

```json
{"customer_id": 42, "query_ids": [1, 2, 3]}
```

**Idempotency key:** `seo_aeo_scan:{customer_id}:{date}`

- [ ] **Step 1:** Handler calls `scan_customer_batch`
- [ ] **Step 2:** Register in worker `elif job_type == "seo_aeo_scan"`
- [ ] **Step 3:** Test `process_seo_aeo_scan_payload` with stub mode

---

### Task 4A-5: Blueprint routes — AEO API

**Files:**
- Modify: `blueprints/seo_aeo.py`

**Routes to add/replace:**

| Method | Path | Handler |
|--------|------|---------|
| GET | `/crm/seo/aeo` | `crm_seo_aeo_console_page` (replace redirect) |
| GET | `/api/v1/seo/clients/<id>/aeo/coverage` | coverage summary |
| GET | `/api/v1/seo/clients/<id>/aeo/queries` | query list + last scan |
| POST | `/api/v1/seo/clients/<id>/aeo/queries` | add query (delegate crm_aeo) |
| DELETE | `/api/v1/seo/clients/<id>/aeo/queries/<qid>` | delete query |
| POST | `/api/v1/seo/clients/<id>/aeo/scan` | single query scan `{query_id}` |
| POST | `/api/v1/seo/clients/<id>/aeo/scan/batch` | enqueue batch |
| GET | `/api/v1/seo/clients/<id>/aeo/mentions` | mention trends |
| POST | `/api/v1/seo/clients/<id>/aeo/queries/<qid>/content` | generate Q&A (delegate crm_aeo) |

**Legacy compat:** Giữ `/api/crm/aeo/*` routes trong `app.py` — thêm deprecation comment.

- [ ] **Step 1:** Replace `crm_seo_aeo_redirect` with template render
- [ ] **Step 2:** Wire API routes with `_can("view")` / `_can("edit")`
- [ ] **Step 3:** Smoke test via curl or pytest blueprint client

---

### Task 4A-6: UI — `crm_seo_aeo_console.html` (S-10)

**Files:**
- Create: `templates/crm_seo_aeo_console.html`
- Create: `static/crm_seo_aeo_console.js`
- Modify: `static/crm_seo.css` (minimal — KPI cards reuse `.agency-stat-card`)

**Wireframe (SPEC_UI_UX §6 S-10):**
- Client selector dropdown
- 4 KPI cards: Coverage %, Readiness avg, Citations/mo, Mentions trend
- Query table: query_text, brand, last_scan, visible badge, actions [Scan] [Q&A] [→ Content]
- Batch scan button + progress (`aria-live="polite"`)
- Link "Tạo content từ gap" → `POST /api/v1/seo/research/to-content` or new content item

- [ ] **Step 1:** HTML shell extends `admin_layout.html`, reuse agency panels
- [ ] **Step 2:** JS: `loadCoverage()`, `loadQueries()`, `batchScan()`, `scanOne(id)`
- [ ] **Step 3:** Coverage badge colors per SPEC §7.1 (≥80 green, 50–79 yellow, <50 red)
- [ ] **Step 4:** Update hub quick-link + sidebar nav to point `/crm/seo/aeo`
- [ ] **Step 5:** `/crm/aeo` legacy page: add banner "Đã chuyển → AEO Console" link

---

### Task 4A-7: Backfill script `migrate_crm_aeo_to_pg.py`

**Files:**
- Create: `scripts/migrate_crm_aeo_to_pg.py`

**Logic:**
1. Read all `crm_aeo_queries` + latest `crm_aeo_scans` from SQLite CRM DB
2. For each scan → INSERT `seo_ai_mentions` (idempotent on `legacy_scan_id`)
3. Optionally INSERT `seo_questions` where `aeo_query_id` not yet linked

- [ ] **Step 1:** `--dry-run` counts rows
- [ ] **Step 2:** `--apply` inserts with ON CONFLICT skip
- [ ] **Step 3:** Document in runbook §8 cutover

---

### Task 4A-8: Hub + report integration

**Files:**
- Modify: `ptt_seo/hub.py` — optional: read coverage from `ptt_seo.aeo.aeo_coverage_summary` instead of inline
- Modify: `ptt_seo/report.py` — dashboard type `aeo` with mention trends
- Modify: `ptt_seo/automation.py` — low coverage alert already exists; add scan-failed alert

- [ ] **Step 1:** Report dashboard `type=aeo` returns coverage + 5 recent mentions
- [ ] **Step 2:** Test in `tests/test_seo_aeo_phase4_aeo_v2.py`

---

### 4A Acceptance checklist

- [ ] `/crm/seo/aeo` renders S-10 (không redirect legacy)
- [ ] Batch scan job completes; mentions visible in PG
- [ ] Coverage KPI khớp legacy calculation
- [ ] Legacy `/crm/aeo` vẫn hoạt động với deprecation banner
- [ ] `pytest tests/test_seo_aeo_phase4_aeo_v2.py` — ≥10 tests pass
- [ ] Stub mode: `PTT_AEO_SCAN_STUB=1` for dev without Anthropic key

---

# Sub-phase 4B — Content Freshness

> Decay scoring từ GSC clicks trend + content age + GA4 sessions drop. Auto-flag `refresh_required` trên pipeline. Weekly systemd timer.

## File map (4B)

| File | Action | Responsibility |
|------|--------|----------------|
| `deploy/sql/seo_aeo_pg_schema.sql` | Modify | `seo_content_freshness` |
| `ptt_seo/freshness.py` | Create | Score algorithm, queue, apply transitions |
| `ptt_seo/connectors/freshness_signals.py` | Create | Pull GSC/GA4 deltas per content URL |
| `ptt_jobs/handlers/seo_freshness_scan.py` | Create | Job handler |
| `ptt_worker/__main__.py` | Modify | Dispatch |
| `blueprints/seo_aeo.py` | Modify | Freshness API + content pipeline filter |
| `templates/crm_seo_content_pipeline.html` | Modify | "Cần refresh" column/filter |
| `static/crm_seo_content.js` | Modify | Show decay score badge |
| `deploy/ptt-seo-freshness-scan.{service,timer}` | Create | Weekly Sunday 04:00 ICT |
| `scripts/sync_seo_freshness_weekly.sh` | Create | CLI entrypoint |
| `tests/test_seo_aeo_phase4_freshness.py` | Create | |

### Task 4B-1: PG schema — `seo_content_freshness`

```sql
CREATE TABLE IF NOT EXISTS seo_aeo.seo_content_freshness (
    id               SERIAL PRIMARY KEY,
    customer_id      INTEGER NOT NULL,
    content_id       INTEGER NOT NULL,
    decay_score      REAL NOT NULL DEFAULT 0,
    traffic_delta_pct REAL,
    age_days         INTEGER NOT NULL DEFAULT 0,
    signals_json     JSONB NOT NULL DEFAULT '{}',
    refresh_priority TEXT NOT NULL DEFAULT 'low',
    last_scored_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, content_id)
);
CREATE INDEX IF NOT EXISTS idx_seo_freshness_priority ON seo_aeo.seo_content_freshness (customer_id, refresh_priority);
```

**Priority bands:**
- `urgent`: decay_score ≥ 80
- `high`: ≥ 60
- `medium`: ≥ 40
- `low`: < 40

- [ ] Append DDL, verify apply

---

### Task 4B-2: Scoring algorithm — `ptt_seo/freshness.py`

**Interfaces:**

```python
def compute_decay_score(
    *,
    age_days: int,
    traffic_delta_pct: float | None,
    gsc_clicks_current: int,
    gsc_clicks_previous: int,
    workflow_status: str,
) -> float:
    """0-100. Higher = staler. Published/monitoring content only."""

def score_content_item(conn, customer_id: int, content_id: int) -> dict[str, Any]: ...

def score_customer_content(customer_id: int) -> dict[str, Any]:
    """Batch all published/monitoring items."""

def apply_refresh_flags(conn, customer_id: int, *, threshold: float = 60.0) -> int:
    """Transition content to refresh_required if decay >= threshold. Returns count."""
```

**Algorithm (YAGNI v1):**

```
base = min(age_days / 365 * 40, 40)          # age component max 40
if traffic_delta_pct is not None:
    drop = max(0, -traffic_delta_pct)       # e.g. -30% → 30
    traffic_component = min(drop, 40)       # max 40
else:
    traffic_component = 0
gsc_decay = 0
if gsc_clicks_previous > 10 and gsc_clicks_current < gsc_clicks_previous * 0.7:
    gsc_decay = 20
decay_score = min(100, base + traffic_component + gsc_decay)
```

- [ ] **Step 1:** Unit tests for `compute_decay_score` edge cases (new content, traffic spike, old stale)
- [ ] **Step 2:** Implement scoring
- [ ] **Step 3:** Test `apply_refresh_flags` transitions only from `published`/`monitoring`

---

### Task 4B-3: Signals connector — map content URL → GSC/GA4

**Files:**
- Create: `ptt_seo/connectors/freshness_signals.py`

**Logic:**
- Join `seo_content.target_url` (or metadata JSON `primary_url`) with `seo_gsc_daily_stats.page`
- Compare clicks sum last 28d vs previous 28d
- GA4: join `landing_page` from `seo_ga4_daily_stats` for sessions delta

- [ ] **Step 1:** Test with seeded in-memory stats rows
- [ ] **Step 2:** Handle missing URL gracefully (decay from age only)

---

### Task 4B-4: Job + systemd timer

**Job type:** `seo_freshness_scan`  
**Payload:** `{"customer_id": 42}` or `{}` for all SEO clients  
**Timer:** Sunday 04:00 ICT (`ptt-seo-freshness-scan.timer`)

- [ ] Create handler + worker dispatch
- [ ] Create `scripts/sync_seo_freshness_weekly.sh`
- [ ] Add to `install_phase3_systemd.sh`
- [ ] Env: `PTT_FRESHNESS_SCAN_ENABLED=1`

---

### Task 4B-5: API + UI

**Routes:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/seo/clients/<id>/freshness` | List scored content sorted by decay |
| POST | `/api/v1/seo/clients/<id>/freshness/scan` | Trigger score job |

**UI changes:**
- Content pipeline: filter tab "Cần refresh" (workflow_status = `refresh_required`)
- Content card badge: `.seo-severity-high` when decay ≥ 60
- Automations page: show freshness scan last run

- [ ] Implement routes
- [ ] Update pipeline template + JS
- [ ] Automation alert rule: `freshness_urgent` when ≥3 items urgent

---

### 4B Acceptance checklist

- [ ] Published content >180 days + traffic drop → `refresh_required`
- [ ] Freshness table populated after scan
- [ ] Pipeline filter shows refresh queue
- [ ] Weekly timer documented in runbook
- [ ] `pytest tests/test_seo_aeo_phase4_freshness.py` — ≥8 tests pass

---

# Sub-phase 4C — Authority & Trust Console

> Track backlinks, citations, brand mentions. CSV import MVP (Ahrefs/Semrush export). UI S-11.

## File map (4C)

| File | Action | Responsibility |
|------|--------|----------------|
| `deploy/sql/seo_aeo_pg_schema.sql` | Modify | `seo_authority_signals` |
| `ptt_seo/authority.py` | Create | CRUD, import, summary |
| `blueprints/seo_aeo.py` | Modify | Authority page + API |
| `templates/crm_seo_authority.html` | Create | S-11 |
| `static/crm_seo_authority.js` | Create | |
| `tests/test_seo_aeo_phase4_authority.py` | Create | |

### Task 4C-1: PG schema — `seo_authority_signals`

```sql
CREATE TABLE IF NOT EXISTS seo_aeo.seo_authority_signals (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    signal_type     TEXT NOT NULL DEFAULT 'backlink',
    source_domain   TEXT NOT NULL DEFAULT '',
    source_url      TEXT NOT NULL DEFAULT '',
    target_url      TEXT NOT NULL DEFAULT '',
    anchor_text     TEXT NOT NULL DEFAULT '',
    domain_rating   REAL,
    status          TEXT NOT NULL DEFAULT 'active',
    first_seen_at   DATE,
    last_seen_at    DATE,
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, signal_type, source_url, target_url)
);
CREATE INDEX IF NOT EXISTS idx_seo_authority_customer ON seo_aeo.seo_authority_signals (customer_id, signal_type);
```

**signal_type enum:** `backlink`, `citation`, `brand_mention`, `pr`

- [ ] Append DDL

---

### Task 4C-2: `ptt_seo/authority.py` — CRUD + CSV import

**Interfaces:**

```python
def list_signals(conn, customer_id: int, *, signal_type: str | None = None) -> list[dict]: ...
def import_backlinks_csv(conn, customer_id: int, csv_text: str) -> dict[str, Any]:
    """Parse Ahrefs/Semrush columns: Referring page URL, Domain rating, Anchor, Target URL."""
def authority_summary(conn, customer_id: int) -> dict[str, Any]:
    """{backlinks_active, backlinks_lost, avg_dr, citations, mentions}."""
```

**CSV column mapping (flexible headers):**
- `Referring page URL` / `Source URL` → source_url
- `Domain rating` / `DR` → domain_rating
- `Anchor` / `Anchor text` → anchor_text
- `Target URL` / `Destination URL` → target_url

- [ ] **Step 1:** Test CSV import with sample 3-row CSV
- [ ] **Step 2:** Test summary counts
- [ ] **Step 3:** Upsert on conflict (update last_seen_at)

---

### Task 4C-3: Blueprint + UI S-11

**Routes:**

| Method | Path |
|--------|------|
| GET | `/crm/seo/authority` |
| GET | `/api/v1/seo/clients/<id>/authority/summary` |
| GET | `/api/v1/seo/clients/<id>/authority/signals` |
| POST | `/api/v1/seo/clients/<id>/authority/import` |

**UI (SPEC wireframe — simplified):**
- Client selector
- KPI: Active backlinks, Avg DR, Citations, Brand mentions
- Table: source_domain, target_url, anchor, DR, status, first_seen
- Import CSV button
- Filter by signal_type tabs

- [ ] Create template + JS
- [ ] Enable sidebar nav item "Authority" (Phase 4 flag)
- [ ] Link from client workspace (future tab)

---

### Task 4C-4: Hub + report integration

- [ ] `seo_hub_summary`: add `authority_backlinks` count per client (optional query)
- [ ] Report dashboard: include authority summary in `executive` type
- [ ] Test hub doesn't break when table empty

---

### 4C Acceptance checklist

- [ ] S-11 page live at `/crm/seo/authority`
- [ ] CSV import Ahrefs format works
- [ ] Summary KPIs accurate
- [ ] Sidebar "Authority" visible
- [ ] `pytest tests/test_seo_aeo_phase4_authority.py` — ≥6 tests pass

---

# Cross-cutting tasks (sau 4A–4C)

### Task X-1: Update master spec §1.6 trạng thái

- Modify: `docs/SPEC_SEO_AEO_OPERATING_SYSTEM.md`
- GSC/GA4 OAuth → ✅, Phase 3.5 code → ✅ (production pending)
- Phase 4 partial → AEO v2 / Freshness / Authority status

### Task X-2: Runbook

- Modify: `docs/runbooks/vps-production-operations.md`
- Add timers: freshness weekly
- Env vars: `PTT_AEO_SCAN_STUB`, `PTT_FRESHNESS_SCAN_ENABLED`

### Task X-3: Full regression

```bash
python3 -m pytest tests/test_seo_aeo_phase1.py tests/test_seo_aeo_phase2.py \
  tests/test_seo_aeo_phase3.py tests/test_seo_aeo_phase4_gsc.py \
  tests/test_seo_aeo_phase4_ga4.py tests/test_seo_aeo_phase4_aeo_v2.py \
  tests/test_seo_aeo_phase4_freshness.py tests/test_seo_aeo_phase4_authority.py \
  tests/test_seo_aeo_pg_cutover.py -q
```

Expected: all pass (PG integration test skipped unless `SEO_AEO_PG_TEST=1`).

---

## Spec self-review

| Spec requirement | Task |
|------------------|------|
| S-10 AEO Console v2 | 4A-6 |
| AEO API §7.5 coverage/scan/mentions | 4A-5 |
| `seo.scan.aeo` job | 4A-4 |
| AEO migration crm_aeo → PG | 4A-7 |
| Content freshness §6.8 | 4B-* |
| `seo.freshness.scan` job | 4B-4 |
| Authority §6.7 | 4C-* |
| S-11 Authority Console | 4C-3 |
| PG-only DDL policy | All schema tasks |
| Flow F4 AEO scan → content gap | 4A-6 link to content |

**Out of scope (Phase 5):** Client portal, experimentation, BI export, entity graph, governance policy engine, Slack alerts.

---

## Execution order (recommended)

```
Week 1:  4A-1 → 4A-2 → 4A-3 → 4A-4
Week 2:  4A-5 → 4A-6 → 4A-7 → 4A-8
Week 3:  4B-1 → 4B-2 → 4B-3 → 4B-4 → 4B-5
Week 4:  4C-1 → 4C-2 → 4C-3 → 4C-4 → X-*
```

**Parallelization:** 4B signals connector can start after 4A-1 if GSC/GA4 data exists. 4C is fully independent after PG cutover.

---

## Lịch sử

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-19 | Initial plan — AEO v2, Freshness, Authority |
