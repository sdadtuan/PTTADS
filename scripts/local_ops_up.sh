#!/usr/bin/env bash
# Start Next.js internal ops console (Phase 0)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OPS_DIR="$ROOT/services/ops-web"

export NEXT_PUBLIC_PTT_API_URL="${NEXT_PUBLIC_PTT_API_URL:-http://127.0.0.1:3000}"
export OPS_PORT="${OPS_PORT:-3200}"

export PTT_STAFF_JWT_SECRET="${PTT_STAFF_JWT_SECRET:-dev-staff-jwt-change-me-min-32-chars}"
export PTT_STAFF_STUB_USERS="${PTT_STAFF_STUB_USERS:-staff@demo.local:demo123:staff-demo-1:1:Demo Staff}"
export PTT_OPS_CORS_ORIGINS="${PTT_OPS_CORS_ORIGINS:-http://127.0.0.1:${OPS_PORT},http://localhost:${OPS_PORT}}"

cd "$OPS_DIR"
if [[ ! -d node_modules ]]; then
  echo "==> npm install (ops-web)"
  npm install
fi

if [[ ! -f .env.local ]]; then
  echo "NEXT_PUBLIC_PTT_API_URL=$NEXT_PUBLIC_PTT_API_URL" > .env.local
  echo "OPS_PORT=$OPS_PORT" >> .env.local
fi

echo "==> ops-web on http://127.0.0.1:$OPS_PORT → API $NEXT_PUBLIC_PTT_API_URL"
echo "    Ensure Nest is up with PTT_STAFF_STUB_USERS (./scripts/local_crm_api_up.sh in another terminal)"
exec npm run dev
