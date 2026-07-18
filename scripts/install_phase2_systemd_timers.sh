#!/usr/bin/env bash
# Install Phase 2 systemd timers on VPS (meta-insights, token-refresh, lead-shadow)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${SYSTEMD_DEST:-/etc/systemd/system}"
UNITS=(
  ptt-lead-shadow-sync.service
  ptt-lead-shadow-sync.timer
  ptt-meta-insights.service
  ptt-meta-insights.timer
  ptt-meta-token-refresh.service
  ptt-meta-token-refresh.timer
  ptt-write-soak.service
  ptt-write-soak.timer
)
echo "==> Copy Phase 2 timer units → $DEST"
for u in "${UNITS[@]}"; do
  src="$ROOT/$u"
  if [[ ! -f "$src" ]]; then
    echo "missing: $src" >&2
    exit 1
  fi
  sudo cp "$src" "$DEST/"
done
sudo systemctl daemon-reload
echo "==> Enable timers"
sudo systemctl enable --now ptt-lead-shadow-sync.timer
sudo systemctl enable --now ptt-meta-insights.timer
sudo systemctl enable --now ptt-meta-token-refresh.timer
sudo systemctl enable --now ptt-write-soak.timer
echo "==> Status"
systemctl list-timers --no-pager 'ptt-lead-shadow-sync.timer' 'ptt-meta-insights.timer' 'ptt-meta-token-refresh.timer' 'ptt-write-soak.timer' || true
echo "Done. Ensure .env: PTT_LEAD_SHADOW_SYNC=1 PTT_META_INSIGHTS_SYNC=1 PTT_META_TOKEN_REFRESH=1 PTT_WRITE_SOAK_LOG=/var/www/ptt/.local-dev/write-soak-evidence.jsonl"
