# Phase 5 — Governance Hub · Client Portal · Experimentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Phase 5 SEO/AEO Enterprise OS — **Governance Hub** (policy engine + publish gates), **Experimentation console** (hypothesis → decision log), **Client portal SEO views** (read-only KPIs + `client_review` approve) — tất cả **PostgreSQL-only**.

**Architecture:** Ba sub-phase độc lập, ship riêng được. Governance hook vào `ptt_seo/content.py` transition/approve. Experimentation là bounded context mới (`ptt_seo/experimentation.py`). Client portal reuse pattern **Creatives** (`ptt-crm-api` Nest + `portal-web` Next.js) với bridge `clients` UUID ↔ `customer_id` SQLite.

**Tech Stack:** Flask 3 (`blueprints/seo_aeo.py`), PostgreSQL `seo_aeo.*`, NestJS `ptt-crm-api`, Next.js `portal-web`, `portal_client_users` JWT, vanilla JS agency tokens, `python3 -m pytest`.

**Prerequisites (blocker):**
- Phase 4 production UAT pass (GSC/GA4 OAuth, AEO v2, Freshness, Authority)
- Phase 3.5 cutover: `SEO_AEO_DB=pg` ≥ 7 ngày soak
- Portal Phase 3 stable: `portal.pttads.vn` login, `portal_client_users` seeded
- 1 pilot: `client_id` UUID ↔ `customer_id` int mapped

**Refs:**
- Master: [`docs/SPEC_SEO_AEO_OPERATING_SYSTEM.md`](../SPEC_SEO_AEO_OPERATING_SYSTEM.md) §9 Phase 5, §11.4
- UI: [`docs/SPEC_UI_UX_SEO_AEO.md`](../SPEC_UI_UX_SEO_AEO.md) S-14, §8.3, §9 permissions
- Architecture: [`docs/specs/2026-07-19-seo-aeo-architecture.md`](../specs/2026-07-19-seo-aeo-architecture.md) §6.12, §14
- PG policy: [`docs/specs/2026-07-19-seo-aeo-pg-cutover-policy.md`](../specs/2026-07-19-seo-aeo-pg-cutover-policy.md)
- Portal pattern: `services/ptt-crm-api/src/creatives/*`, `services/portal-web/src/app/creatives/page.tsx`
- Cutover runbook: [`docs/runbooks/seo-aeo-pg-oauth-uat-cutover.md`](../runbooks/seo-aeo-pg-oauth-uat-cutover.md)

## Global Constraints

- **Storage:** DDL mới chỉ trong `deploy/sql/seo_aeo_pg_schema.sql` + `ptt_seo/pg_schema.py`. Không SQLite SEO schema mới.
- **RBAC CRM:** Section `crm_seo_aeo`; governance override = `_can("configure")` hoặc super-admin. Portal = role `viewer` | `approver` từ JWT.
- **Routes CRM:** Pages `/crm/seo/*`, API `/api/v1/seo/*`.
- **Routes Portal:** Nest `/api/v1/portal/seo/*`, Next `/seo`, `/seo/reports`, `/seo/content`.
- **UI copy:** Tiếng Việt (SPEC_UI_UX §8).
- **Tests:** `tests/test_seo_aeo_phase5_*.py` — TDD per task.
- **Commits:** Chỉ khi user yêu cầu.

---

## Timeline Overview

| Sub-phase | Scope | Effort | Ship criteria |
|-----------|-------|--------|---------------|
| **5A** | Governance Hub + policy engine | ~2 tuần | S-14 live, publish blocked by rules, override audit |
| **5B** | Experimentation console | ~1.5 tuần | CRUD experiments, variants, decision log, hub link |
| **5C** | Client portal SEO | ~2 tuần | Portal `/seo` read-only + client_review approve, E2E |
| **5D** *(stretch)* | BI export hooks | ~1 tuần | Scheduled CSV → object storage — **out of MVP** |

**Total MVP:** ~5–6 tuần (sau Phase 4 prod soak).

**Recommended order:** 5A → 5C (portal cần governance gates) → 5B (có thể song song 5B sau 5A nếu 2 dev).

---

# Sub-phase 5A — Governance Hub

> Screen **S-14** `/crm/seo/governance`. Policy engine chặn publish + hiển thị compliance dashboard. Link `/crm/sop`.

## File map (5A)

| File | Action | Responsibility |
|------|--------|----------------|
| `deploy/sql/seo_aeo_pg_schema.sql` | Modify | `seo_governance_policies`, `seo_governance_evaluations`, `seo_governance_overrides` |
| `ptt_seo/governance.py` | Create | Policy CRUD, evaluate, override, audit |
| `ptt_seo/content.py` | Modify | Hook `evaluate_publish` trước `approved` → `published` |
| `blueprints/seo_aeo.py` | Modify | Governance page + API routes |
| `templates/crm_seo_governance.html` | Create | S-14 UI |
| `static/crm_seo_governance.js` | Create | Client-side |
| `templates/crm_seo_hub.html` | Modify | Link Governance hub (thay SOP-only card) |
| `templates/crm_seo_content_detail.html` | Modify | Policy block modal on transition fail |
| `tests/test_seo_aeo_phase5_governance.py` | Create | Policy + publish gate tests |

### Task 5A-1: PG schema — governance tables

**Files:**
- Modify: `deploy/sql/seo_aeo_pg_schema.sql` (append before `seo_alerts`)
- Modify: `ptt_seo/pg_schema.py` (mirror if needed for tests)

**Interfaces:**
- Produces: tables `seo_governance_policies`, `seo_governance_evaluations`, `seo_governance_overrides`

**DDL to append:**

```sql
CREATE TABLE IF NOT EXISTS seo_aeo.seo_governance_policies (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER,                    -- NULL = global default
    policy_key      VARCHAR(64) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    rule_type       VARCHAR(32) NOT NULL,       -- required_fields | approval_complete | schema_valid | technical_critical | custom
    rule_config     JSONB NOT NULL DEFAULT '{}',
    severity        VARCHAR(16) NOT NULL DEFAULT 'block',  -- block | warn
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, policy_key)
);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_governance_evaluations (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    entity_type     VARCHAR(32) NOT NULL,       -- content | experiment
    entity_id       INTEGER NOT NULL,
    action          VARCHAR(32) NOT NULL,       -- publish | approve
    passed          BOOLEAN NOT NULL,
    violations_json JSONB NOT NULL DEFAULT '[]',
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_seo_gov_eval_entity
    ON seo_aeo.seo_governance_evaluations (customer_id, entity_type, entity_id);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_governance_overrides (
    id              SERIAL PRIMARY KEY,
    evaluation_id   INTEGER NOT NULL REFERENCES seo_aeo.seo_governance_evaluations(id),
    policy_key      VARCHAR(64) NOT NULL,
    actor_id        TEXT NOT NULL DEFAULT '',
    reason          TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- [ ] **Step 1:** Append DDL above to `deploy/sql/seo_aeo_pg_schema.sql`
- [ ] **Step 2:** Run locally:

```bash
export DATABASE_URL=postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency
python3 -c "
from ptt_jobs.db import pg_connection
from ptt_seo.pg_schema import ensure_pg_schema, pg_seo_ready
with pg_connection() as pg:
    ensure_pg_schema(pg)
    assert pg_seo_ready(pg)
print('OK')
"
```

Expected: `OK`

---

### Task 5A-2: `ptt_seo/governance.py` — policy engine core

**Files:**
- Create: `ptt_seo/governance.py`
- Test: `tests/test_seo_aeo_phase5_governance.py`

**Interfaces:**
- Consumes: `seo_read()` / `seo_write()` from `ptt_seo/db.py`; content row dict; `approval_timeline()` from `ptt_seo/workflow.py`
- Produces:
  - `list_policies(conn, *, customer_id: int | None = None) -> list[dict]`
  - `seed_default_policies(conn, customer_id: int | None = None) -> None`
  - `evaluate_content_publish(conn, *, content_id: int) -> dict` → `{ok: bool, violations: list[dict], evaluation_id: int | None}`
  - `record_override(conn, *, evaluation_id: int, policy_key: str, actor_id: str, reason: str) -> int`

**Default policies (seed on first access per customer):**

| policy_key | rule_type | rule_config |
|------------|-----------|-------------|
| `metadata_required` | `required_fields` | `{"fields": ["title", "meta_title", "meta_description", "target_keyword"]}` |
| `qa_complete` | `approval_complete` | `{"stages": ["seo_review", "aeo_review", "technical_review"]}` |
| `no_critical_technical` | `technical_critical` | `{"max_open": 0}` |
| `schema_valid` | `schema_valid` | `{"require_schema_json": true}` |

- [ ] **Step 1: Write failing tests**

```python
# tests/test_seo_aeo_phase5_governance.py
import os, unittest
from ptt_seo.governance import evaluate_content_publish, seed_default_policies

class GovernancePublishGateTests(unittest.TestCase):
    def setUp(self):
        os.environ["SEO_AEO_DB"] = "pg"
        # use PG fixture helper from test_seo_aeo_pg_cutover pattern
        ...

    def test_blocks_publish_without_meta_title(self):
        # insert content missing meta_title, workflow approved
        result = evaluate_content_publish(conn, content_id=1)
        self.assertFalse(result["ok"])
        self.assertTrue(any(v["policy_key"] == "metadata_required" for v in result["violations"]))
```

- [ ] **Step 2:** Run `python3 -m pytest tests/test_seo_aeo_phase5_governance.py -v` — expect FAIL
- [ ] **Step 3:** Implement `governance.py` with rule evaluators (one function per `rule_type`)
- [ ] **Step 4:** Re-run tests — expect PASS
- [ ] **Step 5:** Commit (if requested)

---

### Task 5A-3: Hook content workflow — publish gate

**Files:**
- Modify: `ptt_seo/content.py` — function `transition_status` (~L253)
- Modify: `ptt_seo/content.py` — function `approve_stage` when stage=`client_review` and next=`approved`

**Logic:**

```python
# Before approved → published OR client_review approve → approved:
from ptt_seo.governance import evaluate_content_publish

if target_status == "published" or (stage == "client_review" and approved):
    eval_result = evaluate_content_publish(conn, content_id=content_id)
    if not eval_result["ok"]:
        keys = [v["policy_key"] for v in eval_result["violations"]]
        raise ValueError(f"Governance block: {', '.join(keys)}")
```

- [ ] **Step 1:** Add test `test_transition_to_published_blocked_by_governance` in `test_seo_aeo_phase5_governance.py`
- [ ] **Step 2:** Implement hook in `content.py`
- [ ] **Step 3:** Run `python3 -m pytest tests/test_seo_aeo_phase5_governance.py tests/test_seo_aeo_phase2.py -v -k governance`
- [ ] **Step 4:** Commit (if requested)

---

### Task 5A-4: API routes + Governance Hub UI (S-14)

**Files:**
- Modify: `blueprints/seo_aeo.py`
- Create: `templates/crm_seo_governance.html`
- Create: `static/crm_seo_governance.js`
- Modify: `templates/crm_seo_hub.html` — add card link `/crm/seo/governance`

**API routes:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/crm/seo/governance` | S-14 page |
| GET | `/api/v1/seo/governance/policies` | List policies (`?customer_id=`) |
| POST | `/api/v1/seo/governance/policies` | Upsert policy (configure permission) |
| POST | `/api/v1/seo/governance/evaluate` | `{content_id}` dry-run evaluate |
| POST | `/api/v1/seo/governance/overrides` | Admin override `{evaluation_id, policy_key, reason}` |
| GET | `/api/v1/seo/governance/compliance` | Dashboard: pass rate, recent violations |

**UI sections (ASCII wireframe SPEC S-14):**
1. Compliance KPI row (pass rate 7d, blocked publishes, open overrides)
2. Policy table (toggle active, edit rule_config JSON modal)
3. Recent violations table (content link, rule, severity)
4. Quick link → `/crm/sop`

- [ ] **Step 1:** Add route stubs + empty template
- [ ] **Step 2:** Implement JS fetch policies + compliance
- [ ] **Step 3:** Manual smoke: `/crm/seo/governance?customer_id=1`
- [ ] **Step 4:** Add API tests in `test_seo_aeo_phase5_governance.py`
- [ ] **Step 5:** Commit (if requested)

---

### Task 5A-5: Content detail — governance error UX

**Files:**
- Modify: `templates/crm_seo_content_detail.html`
- Modify: `static/crm_seo_content.js` — on 400 governance error, show modal (SPEC §8.3)

**Modal content:** rule name, missing fields list, [Override] button (admin only, calls override API then retry).

- [ ] **Step 1:** Parse API error `Governance block: metadata_required` → modal
- [ ] **Step 2:** Verify override flow in test or manual UAT checklist
- [ ] **Step 3:** Commit (if requested)

**5A ship gate:**
- [ ] Publish blocked when metadata missing (automated test)
- [ ] Governance hub loads policies + compliance stats
- [ ] Override logged in `seo_governance_overrides`
- [ ] Hub card links to S-14

---

# Sub-phase 5B — Experimentation Console

> Module **6.9** `seo_experiment`. Screen **S-16** `/crm/seo/experiments` (new). Hypothesis → variants → metrics → decision log.

## File map (5B)

| File | Action | Responsibility |
|------|--------|----------------|
| `deploy/sql/seo_aeo_pg_schema.sql` | Modify | `seo_experiments`, `seo_experiment_variants`, `seo_experiment_observations`, `seo_experiment_decisions` |
| `ptt_seo/experimentation.py` | Create | CRUD, status machine, GSC/GA4 metric pull |
| `blueprints/seo_aeo.py` | Modify | Page + API |
| `templates/crm_seo_experiments.html` | Create | List + detail drawer |
| `static/crm_seo_experiments.js` | Create | Client-side |
| `templates/crm_seo_hub.html` | Modify | Quick-link Experiments |
| `tests/test_seo_aeo_phase5_experimentation.py` | Create | Tests |

### Task 5B-1: PG schema — experiment tables

**DDL:**

```sql
CREATE TABLE IF NOT EXISTS seo_aeo.seo_experiments (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    title           VARCHAR(255) NOT NULL,
    hypothesis      TEXT NOT NULL DEFAULT '',
    experiment_type VARCHAR(32) NOT NULL DEFAULT 'content',  -- content | title | schema | landing
    target_url      TEXT NOT NULL DEFAULT '',
    content_id      INTEGER REFERENCES seo_aeo.seo_content(id),
    status          VARCHAR(32) NOT NULL DEFAULT 'draft',
    started_at      TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    owner_id        TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_experiment_variants (
    id              SERIAL PRIMARY KEY,
    experiment_id   INTEGER NOT NULL REFERENCES seo_aeo.seo_experiments(id) ON DELETE CASCADE,
    variant_key     VARCHAR(16) NOT NULL,   -- control | variant_a | variant_b
    label           VARCHAR(255) NOT NULL DEFAULT '',
    config_json     JSONB NOT NULL DEFAULT '{}',
    UNIQUE (experiment_id, variant_key)
);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_experiment_observations (
    id              SERIAL PRIMARY KEY,
    experiment_id   INTEGER NOT NULL REFERENCES seo_aeo.seo_experiments(id) ON DELETE CASCADE,
    variant_key     VARCHAR(16) NOT NULL,
    metric_date     DATE NOT NULL,
    metric_name     VARCHAR(64) NOT NULL,   -- clicks | impressions | ctr | sessions | conversions
    metric_value    DOUBLE PRECISION NOT NULL,
    source          VARCHAR(32) NOT NULL DEFAULT 'manual',  -- manual | gsc | ga4
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (experiment_id, variant_key, metric_date, metric_name)
);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_experiment_decisions (
    id              SERIAL PRIMARY KEY,
    experiment_id   INTEGER NOT NULL REFERENCES seo_aeo.seo_experiments(id) ON DELETE CASCADE,
    decision        VARCHAR(32) NOT NULL,   -- ship | rollback | iterate | inconclusive
    rationale       TEXT NOT NULL DEFAULT '',
    decided_by      TEXT NOT NULL DEFAULT '',
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Status machine:** `draft` → `running` → `completed` | `paused` | `archived`

- [ ] **Step 1:** Append DDL, verify `ensure_pg_schema`
- [ ] **Step 2:** Commit (if requested)

---

### Task 5B-2: `ptt_seo/experimentation.py`

**Interfaces:**
- `create_experiment(conn, customer_id, payload) -> dict`
- `list_experiments(conn, customer_id, *, status=None) -> list[dict]`
- `get_experiment(conn, experiment_id) -> dict | None`
- `transition_experiment(conn, experiment_id, status, *, actor_id='') -> dict`
- `upsert_observation(conn, experiment_id, variant_key, metric_date, metric_name, value, source='manual') -> dict`
- `pull_gsc_metrics(conn, experiment_id, date_from, date_to) -> int` — reads `seo_gsc_daily_stats` for `target_url`
- `record_decision(conn, experiment_id, decision, rationale, decided_by) -> dict`

- [ ] **Step 1:** Write tests in `tests/test_seo_aeo_phase5_experimentation.py`
- [ ] **Step 2:** Implement module
- [ ] **Step 3:** `python3 -m pytest tests/test_seo_aeo_phase5_experimentation.py -v` — PASS
- [ ] **Step 4:** Commit (if requested)

---

### Task 5B-3: UI + API `/crm/seo/experiments`

**API:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/crm/seo/experiments` | Page |
| GET | `/api/v1/seo/clients/:id/experiments` | List |
| POST | `/api/v1/seo/clients/:id/experiments` | Create |
| GET | `/api/v1/seo/experiments/:id` | Detail + variants + observations |
| PATCH | `/api/v1/seo/experiments/:id/status` | Transition |
| POST | `/api/v1/seo/experiments/:id/observations` | Manual metric |
| POST | `/api/v1/seo/experiments/:id/pull-gsc` | Sync metrics from GSC stats |
| POST | `/api/v1/seo/experiments/:id/decisions` | Record decision |

**UI:** Filter by status; table (title, type, status, uplift summary); detail drawer with variant comparison chart (simple bar), decision form.

- [ ] **Step 1:** Routes + template + JS
- [ ] **Step 2:** Hub quick-link
- [ ] **Step 3:** API tests
- [ ] **Step 4:** Commit (if requested)

**5B ship gate:**
- [ ] Create experiment → running → record decision
- [ ] GSC pull populates observations when stats exist
- [ ] Executive report block optional: open experiments count

---

# Sub-phase 5C — Client Portal SEO Views

> **External Next.js** `portal-web`. Read-only SEO/AEO KPIs + content `client_review` approve/reject. Pattern = Creatives module.

## Architecture

```
portal-web (/seo/*)
    → JWT Bearer
    → ptt-crm-api /api/v1/portal/seo/*
        → resolve customer_id via seo_portal_client_map
        → read seo_aeo.* (PG)
        → approve: POST → Flask internal OR direct PG write + audit
```

## File map (5C)

| File | Action | Responsibility |
|------|--------|----------------|
| `deploy/sql/seo_aeo_pg_schema.sql` | Modify | `seo_portal_client_map` |
| `ptt_seo/portal_bridge.py` | Create | UUID ↔ customer_id resolve |
| `services/ptt-crm-api/src/portal-seo/*` | Create | Module (controller, service, repository) |
| `services/ptt-crm-api/src/app.module.ts` | Modify | Import PortalSeoModule |
| `services/portal-web/src/app/seo/page.tsx` | Create | SEO dashboard |
| `services/portal-web/src/app/seo/reports/page.tsx` | Create | Read-only report |
| `services/portal-web/src/app/seo/content/page.tsx` | Create | Pending client_review list |
| `services/portal-web/src/app/seo/content/[id]/page.tsx` | Create | Approve/reject |
| `services/portal-web/src/components/PortalNav.tsx` | Modify | SEO nav item |
| `services/portal-web/src/lib/api.ts` | Modify | Portal SEO API client |
| `services/portal-web/e2e/portal-seo.spec.ts` | Create | Playwright E2E |
| `scripts/seed_portal_seo_pilot_map.py` | Create | Map pilot UUID → customer_id |
| `tests/test_seo_aeo_phase5_portal_bridge.py` | Create | Bridge unit tests |

### Task 5C-1: Client ↔ customer bridge table

**DDL:**

```sql
CREATE TABLE IF NOT EXISTS seo_aeo.seo_portal_client_map (
    client_id       UUID PRIMARY KEY,
    customer_id     INTEGER NOT NULL UNIQUE,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Seed example:**

```python
# scripts/seed_portal_seo_pilot_map.py
MAPS = [
    ("550e8400-e29b-41d4-a716-446655440000", 1),  # pilot1 → crm customer 1
]
```

- [ ] **Step 1:** DDL + seed script
- [ ] **Step 2:** `ptt_seo/portal_bridge.py`:

```python
def customer_id_for_portal_client(conn, client_id: str) -> int | None: ...
def portal_client_for_customer(conn, customer_id: int) -> str | None: ...
```

- [ ] **Step 3:** Tests PASS
- [ ] **Step 4:** Commit (if requested)

---

### Task 5C-2: NestJS `portal-seo` module

**Files:**
- Create: `services/ptt-crm-api/src/portal-seo/portal-seo.module.ts`
- Create: `services/ptt-crm-api/src/portal-seo/portal-seo.controller.ts`
- Create: `services/ptt-crm-api/src/portal-seo/portal-seo.service.ts`
- Create: `services/ptt-crm-api/src/portal-seo/portal-seo.repository.ts`
- Create: `services/ptt-crm-api/src/portal-seo/portal-seo.types.ts`

**Endpoints (all `@UseGuards(PortalJwtGuard)`):**

| Method | Path | Role | Purpose |
|--------|------|------|---------|
| GET | `/api/v1/portal/seo/summary` | viewer+ | KPIs: organic sessions, AEO coverage, open issues |
| GET | `/api/v1/portal/seo/reports/executive` | viewer+ | Read-only executive report JSON |
| GET | `/api/v1/portal/seo/content/pending-review` | viewer+ | `workflow_status=client_review` |
| GET | `/api/v1/portal/seo/content/:id` | viewer+ | Content detail (no internal notes) |
| POST | `/api/v1/portal/seo/content/:id/review` | **approver** | `{approved: bool, notes: string}` |

**Review implementation:** Call PG update + `seo_content_approvals` insert + governance re-check (must pass before approve). Reuse SQL from `ptt_seo/content.py` `approve_stage` logic — extract shared function or HTTP call to Flask:

```bash
# Option A (recommended MVP): duplicate minimal approve SQL in repository
# Option B: Flask internal POST /api/v1/seo/internal/portal-approve with service token
```

Use **Option A** for MVP; refactor to shared Python module in 5C-3 if drift risk.

- [ ] **Step 1:** Repository queries against `seo_aeo.seo_*` with `customer_id` filter
- [ ] **Step 2:** Controller + role check (`approver` for POST review)
- [ ] **Step 3:** Unit tests `portal-seo.service.spec.ts`
- [ ] **Step 4:** Commit (if requested)

---

### Task 5C-3: Next.js portal pages

**Pages:**

| Route | Component | Data |
|-------|-----------|------|
| `/seo` | SEO dashboard | `portalSeoSummary()` |
| `/seo/reports` | Executive report | `portalSeoExecutiveReport()` |
| `/seo/content` | Pending review table | `portalSeoPendingContent()` |
| `/seo/content/[id]` | Detail + Approve/Reject | `portalSeoContent(id)`, `portalSeoReview(id, body)` |

**PortalNav:** add link "SEO/AEO" when summary returns `seo_enabled: true`.

**Permissions (SPEC §9):**
- `viewer`: read all SEO pages, no approve button
- `approver`: approve/reject on content detail

- [ ] **Step 1:** Extend `src/lib/api.ts` with portal SEO functions
- [ ] **Step 2:** Build 4 pages (reuse `PerformancePanel` styling patterns)
- [ ] **Step 3:** Update `PortalNav.tsx`
- [ ] **Step 4:** Commit (if requested)

---

### Task 5C-4: E2E + production cutover

**E2E** (`services/portal-web/e2e/portal-seo.spec.ts`):
1. Login as `approver.pilot1@pttads.vn`
2. Navigate `/seo/content`
3. Open first pending item → Approve
4. Verify status change via API

**Production checklist** (append to [`seo-aeo-pg-oauth-uat-cutover.md`](../runbooks/seo-aeo-pg-oauth-uat-cutover.md) §9):

```bash
# Map pilot client
python3 scripts/seed_portal_seo_pilot_map.py --apply

# Deploy Nest + portal-web
sudo systemctl restart ptt-crm-api
cd services/portal-web && npm run build && pm2 restart portal-web  # or systemd unit

# Smoke
curl -sf -H "Authorization: Bearer $TOKEN" \
  https://portal.pttads.vn/api/v1/portal/seo/summary
```

- [ ] **Step 1:** Playwright test green locally
- [ ] **Step 2:** Runbook section added
- [ ] **Step 3:** Pilot UAT sign-off

**5C ship gate:**
- [ ] Portal viewer sees KPIs + reports (no write)
- [ ] Portal approver completes client_review
- [ ] Governance blocks approve if policies fail
- [ ] CRM staff see approval in content timeline

---

# Cross-cutting tasks

### Task X-1: RBAC + nav

**Files:**
- Modify: `admin_page_permissions.py` — ensure `crm_seo_aeo` + optional `crm_seo_aeo_governance`
- Modify: CRM sidebar template — enable Governance + Experiments items (remove "Phase 5" tooltip when shipped)

- [ ] Verify permission matrix SPEC §9
- [ ] Commit (if requested)

### Task X-2: Feature flags

**Env vars:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `PTT_SEO_GOVERNANCE_ENABLED` | `1` | Policy engine active |
| `PTT_SEO_EXPERIMENTS_ENABLED` | `0` | Experiments UI (enable after 5B) |
| `PTT_PORTAL_SEO_ENABLED` | `0` | Portal SEO nav + API |

- [ ] **Step 1:** Guard routes with env checks
- [ ] **Step 2:** Document in `.env.example` + runbook

### Task X-3: Full test suite

```bash
export DATABASE_URL=postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency
export SEO_AEO_DB=pg
python3 -m pytest tests/test_seo_aeo_phase5_*.py tests/test_seo_aeo_phase4_*.py -v
cd services/ptt-crm-api && npm test -- --testPathPattern=portal-seo
cd services/portal-web && npm run test:e2e -- --grep portal-seo
```

Expected: all PASS

### Task X-4: Update master spec §1.6

**Files:**
- Modify: `docs/SPEC_SEO_AEO_OPERATING_SYSTEM.md` — mark Phase 5 items when shipped
- Modify: `docs/SPEC_UI_UX_SEO_AEO.md` §11 — Phase 5 screens enabled

---

# Production rollout sequence

```
Week 1–2   5A Governance (staging UAT: publish gates)
Week 2–3   5C Portal bridge + Nest API (staging, viewer role)
Week 3–4   5C Portal UI + approver UAT (1 pilot client)
Week 4–5   5B Experiments (internal team first)
Week 5–6   Prod cutover: flags ON, soak 7 days, sign-off
```

**Order on prod:**
1. Deploy DDL (governance + experiments + bridge) — idempotent
2. `PTT_SEO_GOVERNANCE_ENABLED=1` — monitor blocked publishes
3. `seed_portal_seo_pilot_map.py` for pilot
4. `PTT_PORTAL_SEO_ENABLED=1` — portal smoke
5. `PTT_SEO_EXPERIMENTS_ENABLED=1` — internal only initially

**Rollback:**

| Component | Action |
|-----------|--------|
| Governance | `PTT_SEO_GOVERNANCE_ENABLED=0` — transitions unblocked |
| Portal SEO | `PTT_PORTAL_SEO_ENABLED=0` — hide nav; CRM approve still works |
| Experiments | `PTT_SEO_EXPERIMENTS_ENABLED=0` — hide UI; data retained |

---

# Definition of Done (Phase 5 gate)

- [ ] Production `SEO_AEO_DB=pg` (prerequisite unchanged)
- [ ] Governance hub UAT: 4 default policies enforce publish rules
- [ ] 1 pilot client portal: viewer + approver roles tested E2E
- [ ] Client approve triggers governance + audit log
- [ ] ≥1 experiment completed with decision log (internal pilot)
- [ ] No P1 incidents 7 ngày post-cutover
- [ ] Master spec §1.6 + UI spec §11 updated

---

# Out of scope (Phase 5 MVP)

- BI warehouse export / ClickHouse SEO facts (Phase 5D stretch)
- Entity graph visualization (Phase 4+ future)
- Slack alert channel for governance violations
- Keycloak SSO for portal (ADR-011 future)
- Automated A/B traffic splitting (experiments = tracking + decision log only)

---

## Lịch sử

| Date | Change |
|------|--------|
| 2026-07-19 | Initial Phase 5 plan — Governance, Experimentation, Client portal |
