#!/usr/bin/env bash
# Install Gate D (+ optional SERP) systemd timers on VPS
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

UNITS=(
  ptt-seo-gate-d.service
  ptt-seo-gate-d.timer
  ptt-seo-serp-capture.service
  ptt-seo-serp-capture.timer
)

for unit in "${UNITS[@]}"; do
  src="$ROOT/deploy/$unit"
  if [[ ! -f "$src" ]]; then
    echo "WARN  missing deploy/$unit — skip" >&2
    continue
  fi
  echo "==> cp $unit"
  cp "$src" "/etc/systemd/system/$unit"
  chmod 644 "/etc/systemd/system/$unit"
done

chmod +x "$ROOT/scripts/seo_aeo_cron_gate_d.sh" 2>/dev/null || true
chmod +x "$ROOT/scripts/sync_seo_serp_weekly.sh" 2>/dev/null || true

systemctl daemon-reload
systemctl enable ptt-seo-gate-d.timer
if [[ -f /etc/systemd/system/ptt-seo-serp-capture.timer ]]; then
  systemctl enable ptt-seo-serp-capture.timer
fi

echo "OK  Gate D systemd installed."
echo "    sudo systemctl start ptt-seo-gate-d.timer"
echo "    sudo systemctl start ptt-seo-gate-d.service   # one-shot smoke"
echo "    systemctl list-timers --no-pager 'ptt-seo-gate-d*'"
