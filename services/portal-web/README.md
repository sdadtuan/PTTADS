# PTT Client Portal (Next.js)

Phase 3 spike — login via Nest JWT, dashboard placeholder for CPL/performance.

## Prerequisites

- Node.js ≥ 22
- Nest `ptt-crm-api` on `:3000` with portal auth (Sprint 0):

```bash
export PTT_PORTAL_JWT_SECRET=dev-portal-jwt-change-me-min-32-chars
export PTT_PORTAL_STUB_USERS=viewer@demo.local:demo123:550e8400-e29b-41d4-a716-446655440000:viewer
export PTT_PORTAL_CORS_ORIGINS=http://127.0.0.1:3100,http://localhost:3100
./scripts/local_crm_api_up.sh
```

## Local dev

```bash
cp .env.example .env.local   # optional
./scripts/local_portal_up.sh
# → http://127.0.0.1:3100/login
# viewer@demo.local / demo123
```

Or from this directory:

```bash
npm install
npm run dev
```

## Build (VPS standalone)

```bash
npm run build
# Output: .next/standalone — see deploy/runbook portal.pttads.vn
node .next/standalone/server.js
```

## Routes

| Path | Description |
|------|-------------|
| `/login` | Client login → Nest `POST /api/v1/portal/auth/login` |
| `/dashboard` | Profile + API health (performance API Phase 3 P3) |

## Env

| Variable | Default |
|----------|---------|
| `NEXT_PUBLIC_PTT_API_URL` | `http://127.0.0.1:3000` |
| `PORTAL_PORT` | `3100` |

Nest (not Next): `PTT_PORTAL_CORS_ORIGINS`, `PTT_PORTAL_STUB_USERS`, `PTT_PORTAL_JWT_SECRET`.
