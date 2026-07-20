# PTT Ops Web (Phase 0)

Internal staff console at `ops.pttads.vn` — replaces Flask admin UI over time.

## Local dev

```bash
# Terminal 1 — Nest API with staff stub user
export PTT_STAFF_JWT_SECRET=dev-staff-jwt-change-me-min-32-chars
export PTT_STAFF_STUB_USERS=staff@demo.local:demo123:staff-demo-1:1:Demo Staff
export PTT_OPS_CORS_ORIGINS=http://127.0.0.1:3200,http://localhost:3200
./scripts/local_crm_api_up.sh

# Terminal 2 — ops-web
./scripts/local_ops_up.sh
```

Login: `staff@demo.local` / `demo123`

## Routes (Phase 0)

| Route | Description |
|-------|-------------|
| `/login` | Staff login |
| `/` | Dashboard placeholder |
| `/crm/leads` | Lead list (Nest PG read) |
