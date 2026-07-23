# Wave B7 — Offboarding + Flask retire (Phase 5)

> **PO scope (2026-07-23):** `b7_doc` · `offboard_pro` · `portal_done` · `flask_retire` · **go (spec only)**  
> **Master refs:** FR-CL-03 / FR-03 · [`SPEC_MIGRATION_FLASK_EXECUTION_PLAN.md`](../SPEC_MIGRATION_FLASK_EXECUTION_PLAN.md) §10 · [`phase5-flask-retirement-checklist.md`](../runbooks/phase5-flask-retirement-checklist.md)

## Goal

Đóng vòng **client lifecycle** (offboard có audit) và **retire Flask monolith** trên prod — HTTP chỉ qua Nest + Next (ops-web, portal-web). Wave B7 là **cutover wave**: phần lớn script/gate đã có từ Phase 3–5; slice code mới chủ yếu **B7.1**.

## Wave map

| ID | Hành động | Trạng thái repo | Gate / evidence |
|----|-----------|-----------------|-----------------|
| **B7.1** | Offboard client | **Thiết kế — chưa code** | API + audit + event |
| **B7.2** | Portal prod cutover | **Done (B6-S7)** | Phase 3 UAT sign-off |
| **B7.3** | Flask readonly soak | Script/env có | PO: đã soak ≥14d → skip hoặc artifact |
| **B7.4** | Stop `ptt.service` | `close_flask_retirement.sh` | `phase5_flask_retirement_gates` |
| **B7.5** | nginx remove Flask upstream | `nginx-rs-flask-retired.conf` | POST không 503 |

---

## B7.1 — Offboard client (`offboard_pro`)

### Nghiệp vụ

Khi AM chấm dứt hợp đồng client:

1. **Revoke tokens** — mọi `client_channel_accounts` (meta/google): vault clear + `token_status=revoked`
2. **Portal lock** — `portal_client_users.active=false`; refresh tokens vô hiệu (không cấp JWT mới)
3. **Status** — `clients.status`: `active|paused|…` → `offboarding` → `archived`
4. **Event** — emit `ClientOffboarded` (catalog v1)
5. **Audit** — bản ghi bất biến ai/when/why
6. **RLS stub** — tenant lock để query PG scoped theo `client_id` từ chối write (Phase 5.1 full RLS)

### API (đề xuất — slice B7.1-S1)

| Method | Route | Cap | Mô tả |
|--------|-------|-----|-------|
| `POST` | `/api/v1/clients/:id/offboard` | `crm_agency` configure | Bắt đầu offboard (idempotent) |
| `GET` | `/api/v1/clients/:id/offboard/audit` | `crm_agency` view | Lịch sử offboard |

**Body `POST offboard`:**

```json
{
  "reason": "contract_ended",
  "note": "Hết hạn Q4/2026",
  "archive_data": true
}
```

**Response:** `{ ok, client_id, status, tokens_revoked, portal_users_deactivated, event_id, audit_id }`

### Service flow

```mermaid
sequenceDiagram
  participant AM as Agency Ops
  participant Nest as ptt-crm-api
  participant PG as PostgreSQL
  participant EV as domain_events

  AM->>Nest: POST /clients/:id/offboard
  Nest->>PG: BEGIN; status=offboarding
  Nest->>PG: revoke channel tokens (all channels)
  Nest->>PG: portal_client_users.active=false
  Nest->>EV: ClientOffboarded
  Nest->>PG: client_offboard_audit INSERT
  Nest->>PG: status=archived; COMMIT
  Nest-->>AM: 200 + audit_id
```

### DDL (B7.1-S1)

```sql
CREATE TABLE IF NOT EXISTS client_offboard_audit (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients (id),
    initiated_by    TEXT NOT NULL,
    reason          VARCHAR(64) NOT NULL,
    note            TEXT,
    tokens_revoked  INT NOT NULL DEFAULT 0,
    portal_users_deactivated INT NOT NULL DEFAULT 0,
    previous_status VARCHAR(32),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### RLS stub (không full PG RLS trong B7.1)

- Cột `clients.tenant_locked BOOLEAN DEFAULT FALSE` — set `true` khi archived
- Middleware Nest: mọi mutation scoped route check `tenant_locked` → `403 tenant_archived`
- Document path tới full RLS policy (Phase 6)

### Reuse hiện có

- Revoke token: `agency.repository.ts` `patchChannelAccount({ revoke: true })`
- Client status: `clients.status` enum đã có `offboarding`, `archived` (DDL v1)
- Event: `ClientOffboarded` trong [`events/catalog.yaml`](events/catalog.yaml)

### Out of scope B7.1-S1

- Xóa PG data (chỉ archive + lock)
- Meta/Google API revoke OAuth server-side (chỉ vault local + status)
- Temporal cancel workflows (subscriber Phase 5.2)

---

## B7.2 — Portal prod cutover (`portal_done`)

**Baseline:** Wave B6-S7 (`49ec252`) — portal JWT refresh, middleware, settings, creative history, export.

### Checklist (human + automated)

| Step | Command / artifact |
|------|-------------------|
| DDL branding | `psql $DATABASE_URL -f docs/specs/2026-07-23-postgresql-ddl-v3-portal-settings.sql` |
| Env prod | `deploy/env.phase3-prod.example` — `PTT_PORTAL_AUTH_MODE=dual`, stub off |
| Gate auto | `./scripts/phase3_prod_uat_gate.sh` |
| Gate pack | `python3 -m ptt_crm.phase3_portal_gates` (P3-G01..G10) |
| E2E | `./scripts/playwright_portal_e2e_temporal.sh` |
| Human sign-off | `docs/evidence/phase3-uat-signoff.json` (AM, approver pilot, DevOps, QA) |
| Canonical URL | `https://portal.pttads.vn` — nginx `deploy/nginx-portal.conf` |

**DoD B7.2:** UAT sign-off 4/4 + portal gate `ok: true` trên prod.

---

## B7.3 — Flask readonly soak

PO xác nhận **đã soak ≥14 ngày** → có thể **bỏ qua timer** nếu có artifact:

- Ghi `docs/evidence/flask-readonly-soak.json` với `started_at`, `ended_at`, `days≥14`
- Hoặc set `PHASE5_SKIP_SOAK=1` khi chạy gate (chỉ khi PO đã approve)

Nếu cần chạy lại soak:

```bash
# .env prod
PTT_FLASK_MONOLITH_MODE=readonly
# Giữ ptt.service active; monitor 14 ngày
./scripts/crm_flask_migration_pack.sh phase5-dry  # must PASS trước retire
```

---

## B7.4 — Stop `ptt.service` (`flask_retire`)

### Prerequisites (hard)

- [ ] B7.2 UAT sign-off
- [ ] `PTT_LEADS_WRITE_SOURCE=pg`, `PTT_WEBHOOKS_FLASK_FALLBACK=0`
- [ ] `./scripts/staging_phase5_gate_pack.sh` → `ok: true`
- [ ] `./scripts/crm_flask_migration_pack.sh phase5-dry` → PASS

### Cutover

```bash
set -a && source deploy/env.phase5-flask-retire.example && set +a
# Chỉnh secrets trên VPS

sudo -E ./scripts/close_flask_retirement.sh              # dry-run
sudo -E APPLY=1 ./scripts/close_flask_retirement.sh      # B7.4 execute
```

Script sets `PTT_FLASK_MONOLITH_MODE=retired`, stops/disables `ptt.service`, restarts Nest/worker/ops-web/portal-web.

**Gate:** `python3 -m ptt_crm.phase5_flask_retirement_gates` → `.local-dev/phase5-flask-retirement-gate-report.json`

---

## B7.5 — nginx remove Flask upstream

Included in `close_flask_retirement.sh` APPLY:

- Deploy `deploy/nginx-rs-flask-retired.conf` → `rs.pttads.vn`
- Flask upstream `:8002` removed; redirect/302 tới ops-web where needed

### Verification (không 503 trên POST)

| Check | Expected |
|-------|----------|
| `curl -sf http://127.0.0.1:3000/health` | 200 |
| `curl -X POST https://rs.pttads.vn/api/v1/leads/...` (staff JWT) | 2xx via Nest, not 503 |
| `systemctl is-active ptt.service` | inactive |
| Meta webhook test | job_queue row, no 502 |
| ops-web `/crm/leads` | 200 |
| portal `/dashboard` | 200 |

---

## Implementation slices (post-spec)

| Slice | Deliverable | Depends |
|-------|-------------|---------|
| **B7.1-S1** | Offboard API + audit DDL + ops-web button + gate | Spec approved |
| **B7.2-S1** | UAT evidence template update + prod gate script wrapper | B6-S7 deployed |
| **B7.4-S1** | VPS APPLY + post-cutover smoke | B7.2 + phase5 dry |
| **B7-G** | `wave_b7_gates.py` + `wave_b7_smoke.sh` | B7.1 code landed |

---

## Rollback

| Step | Rollback |
|------|----------|
| B7.4 Flask stop | `systemctl enable --now ptt.service`; `PTT_FLASK_MONOLITH_MODE=readonly` |
| nginx | Restore `${NGINX_SITE}.pre-phase5.bak` |
| B7.1 offboard | Manual status revert + re-enable portal users (no auto undelete) |
| Portal | `docs/runbooks/vps-phase3-portal-cutover-checklist.md` § Rollback |

---

## Env summary (prod retire)

See `deploy/env.phase5-flask-retire.example`:

- `PTT_FLASK_MONOLITH_MODE=retired`
- `PTT_WEBHOOKS_FLASK_FALLBACK=0`
- `PTT_PORTAL_SEO_ENABLED=1`
- Services kept: `ptt-crm-api`, `ptt-worker`, `ptt-fb-autosync`, `ptt-temporal-worker`, `ptt-ops-web`, `ptt-portal-web`

---

## Lịch sử

| Ngày | Ghi chú |
|------|---------|
| 2026-07-23 | Wave B7 spec — PO: doc only, offboard_pro design, portal done, flask retire ready |
