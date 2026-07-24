# Pull Request: Merge Meta Enterprise B12 Creative Registry into `main`

Use this document when opening the PR on GitHub.

| Field | Value |
|-------|-------|
| **Title** | feat(meta-b12): ad_id ↔ creative asset registry |
| **Base** | `main` |
| **Compare** | `feat/meta-b12-creative-registry` |
| **Remote** | https://github.com/sdadtuan/PTTADS |
| **Create PR** | https://github.com/sdadtuan/PTTADS/compare/main...feat/meta-b12-creative-registry?expand=1 |

---

## Summary

- **B12 core (ME45)** — PostgreSQL DDL v9 `meta_ad_creative_links`, Python `creative_registry.py`, Nest `meta-creative-registry` API, CRM Creative Hub link panel.
- **Bridge for B15** — Registry maps Meta `external_ad_id` → approved `creative_submissions` asset; supports manual link now, Graph creative id field reserved for B15 upload/edit.

**Scope:** 26 files, +1,648 lines (2 commits ahead of `main`).

### Commits included

- `9589022` — feat(meta-b12): add ad_id ↔ creative asset registry
- `acd021f` — docs(pr): add B12 creative registry merge checklist for main

---

## API (Nest)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/meta/creative-links` | Filter by client, ad, campaign, creative |
| GET | `/api/v1/meta/creative-links/resolve` | Resolve active link for ad |
| POST | `/api/v1/meta/creative-links` | Link approved creative ↔ ad_id |
| DELETE | `/api/v1/meta/creative-links/:id` | Soft-deactivate link |

Feature flag: `PTT_META_CREATIVE_REGISTRY_ENABLED=0` (default off).

---

## ops-web

- **CRM Creative Hub** (`/crm/creatives`) — approved rows show **Meta ad link** panel
- Flag: `NEXT_PUBLIC_PTT_META_CREATIVE_REGISTRY_ENABLED=0`
- Caps: `canEditMetaCreativeRegistry` (`crm_facebook_ads.edit` or lifecycle write)

---

## Pre-merge checklist (reviewer)

- [ ] DDL order: **v3 creatives → v9 B12 registry**
- [ ] Feature flag default **off** (`PTT_META_CREATIVE_REGISTRY_ENABLED=0`)
- [ ] `./scripts/wave_b12_gate.sh` PASS (B12-G01..G05)
- [ ] B11 regression via B12-G04
- [ ] Link requires `creative_submissions.status=approved`
- [ ] No secrets in `deploy/env.meta-enterprise-b12.example`

---

## Deploy plan (post-merge)

### 1. Pull code

```bash
cd /var/www/ptt
git pull origin main
```

### 2. Apply PostgreSQL DDL

```bash
./scripts/apply_pg_ddl_v3_creatives.sh          # if not yet applied
./scripts/apply_pg_ddl_v9_meta_creative_registry.sh
```

### 3. Environment (pilot — flag off first)

Copy `deploy/env.meta-enterprise-b12.example` into `.env`, then enable after DDL + smoke:

```bash
PTT_META_CREATIVE_REGISTRY_ENABLED=0
NEXT_PUBLIC_PTT_META_CREATIVE_REGISTRY_ENABLED=0
```

Enable per pilot client:

```bash
PTT_META_CREATIVE_REGISTRY_ENABLED=1
NEXT_PUBLIC_PTT_META_CREATIVE_REGISTRY_ENABLED=1
```

### 4. Build & restart

```bash
cd services/ptt-crm-api && npm run build
cd ../ops-web && npm run build
# restart services
```

### 5. Smoke

```bash
./scripts/wave_b12_gate.sh
./scripts/wave_b12_smoke.sh
```

---

## Test plan

- [ ] `./scripts/wave_b12_gate.sh` — B12-G01..G05 PASS
- [ ] `python3 -m unittest tests.test_creative_registry tests.test_b12_creative_registry_qa -v`
- [ ] `cd services/ptt-crm-api && npm test -- --testPathPattern=meta-creative-registry`
- [ ] `cd services/ops-web && npm run build`
- [ ] Manual: `/crm/creatives` — approved creative → link ad_id → resolve API returns asset
- [ ] Regression: `./scripts/wave_b11_gate.sh` (or via B12-G04)

---

## Rollback

Set flags off (no DDL rollback required):

```bash
PTT_META_CREATIVE_REGISTRY_ENABLED=0
NEXT_PUBLIC_PTT_META_CREATIVE_REGISTRY_ENABLED=0
```

Existing registry rows are preserved for audit.
