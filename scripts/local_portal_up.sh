#!/usr/bin/env bash
# Start Next.js client portal (Phase 3 spike)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORTAL_DIR="$ROOT/services/portal-web"

export NEXT_PUBLIC_PTT_API_URL="${NEXT_PUBLIC_PTT_API_URL:-http://127.0.0.1:3000}"
export PORTAL_PORT="${PORTAL_PORT:-3100}"

# Nest portal auth (match deploy/env.sprint0.example stub user)
export PTT_PORTAL_JWT_SECRET="${PTT_PORTAL_JWT_SECRET:-dev-portal-jwt-change-me-min-32-chars}"
export PTT_PORTAL_STUB_USERS="${PTT_PORTAL_STUB_USERS:-viewer@demo.local:demo123:550e8400-e29b-41d4-a716-446655440000:viewer,approver@demo.local:demo123:550e8400-e29b-41d4-a716-446655440000:approver}"
export PTT_PORTAL_CORS_ORIGINS="${PTT_PORTAL_CORS_ORIGINS:-http://127.0.0.1:${PORTAL_PORT},http://localhost:${PORTAL_PORT}}"

cd "$PORTAL_DIR"
if [[ ! -d node_modules ]]; then
  echo "==> npm install (portal-web)"
  npm install
fi

if [[ ! -f .env.local ]]; then
  echo "NEXT_PUBLIC_PTT_API_URL=$NEXT_PUBLIC_PTT_API_URL" > .env.local
  echo "PORTAL_PORT=$PORTAL_PORT" >> .env.local
fi

echo "==> portal-web on http://127.0.0.1:$PORTAL_PORT → API $NEXT_PUBLIC_PTT_API_URL"
echo "    Ensure Nest is up with PTT_PORTAL_STUB_USERS (./scripts/local_crm_api_up.sh in another terminal)"
exec npm run dev
