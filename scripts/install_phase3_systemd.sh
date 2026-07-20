#!/usr/bin/env bash
# Install Phase 3 systemd units (portal, temporal worker, google insights) on VPS
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

UNITS=(
  ptt-portal-web.service
  ptt-temporal-worker.service
  ptt-google-insights.service
  ptt-google-insights.timer
  ptt-seo-gsc-sync.service
  ptt-seo-gsc-sync.timer
  ptt-seo-ga4-sync.service
  ptt-seo-ga4-sync.timer
  ptt-seo-freshness-scan.service
  ptt-seo-freshness-scan.timer
)

for unit in "${UNITS[@]}"; do
  src="$ROOT/deploy/$unit"
  if [[ ! -f "$src" ]]; then
    src="$ROOT/$unit"
  fi
  if [[ ! -f "$src" ]]; then
    echo "WARN  missing $unit — skip" >&2
    continue
  fi
  echo "==> cp $unit"
  cp "$src" "/etc/systemd/system/$unit"
done

systemctl daemon-reload
systemctl enable ptt-portal-web.service ptt-temporal-worker.service ptt-google-insights.timer ptt-seo-gsc-sync.timer ptt-seo-ga4-sync.timer ptt-seo-freshness-scan.timer
echo "OK  Phase 3 units installed. Start:"
echo "    systemctl start ptt-portal-web ptt-temporal-worker"
echo "    systemctl start ptt-google-insights.timer"
echo "    systemctl start ptt-seo-gsc-sync.timer"
echo "    systemctl start ptt-seo-ga4-sync.timer"
echo "    systemctl start ptt-seo-freshness-scan.timer"
