#!/usr/bin/env bash
# Cắt video Like Page PTT 20s từ file gốc theo storyboard.
# Usage: ./scripts/cut_like_page_video_20s.sh [path/to/source.mp4]

set -euo pipefail

SRC="${1:-/Users/quoctuan/Downloads/PTT Advertising Solutions.mp4}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/output/video_like_page_20s"
CLIPS="$OUT/clips"

if [[ ! -f "$SRC" ]]; then
  echo "Không tìm thấy file nguồn: $SRC" >&2
  exit 1
fi

mkdir -p "$CLIPS"

# Filter chuẩn hóa: 1080x1080, 30fps, H.264 (Meta-friendly)
VF='scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30'
ENC=(-c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 128k -ar 44100 -ac 2)

cut_clip() {
  local name="$1" ss="$2" dur="$3"
  echo "→ $name  (ss=${ss}s  t=${dur}s)"
  ffmpeg -y -hide_banner -loglevel error \
    -ss "$ss" -i "$SRC" -t "$dur" \
    -vf "$VF" "${ENC[@]}" \
    -movflags +faststart \
    "$CLIPS/${name}.mp4"
}

echo "=== Bước 1: Cắt từng đoạn từ video gốc ==="

# Timeline storyboard → timestamp file gốc (~47s)
# 0-2s   Hook logo      → end card đầu (tránh báo Melbourne 0-10s)
cut_clip "01_hook_logo_endcard"   43.5  2.0
# 2-3s   Hook boardroom → có phụ đề VN "Thu hút đúng khách hàng..."
cut_clip "02_hook_boardroom"      10.0  1.5
# 3-6s   Performance    → skyscraper + boardroom
cut_clip "03_performance_sky"      5.0  2.0
cut_clip "04_performance_room"    12.0  2.0
# 6-7s   Transition     → flash nhanh từ skyscraper (hoặc bỏ khi ghép)
cut_clip "05_transition_flash"     8.5  0.5
# 7-10s  CRM+Automation
cut_clip "06_crm_automation"      15.0  3.5
# 10-11s Icon row      → giữ 1 frame cuối CRM (freeze trong bước 2 tuỳ chọn)
cut_clip "07_services_hold"       18.0  1.0
# 11-12s Transition
cut_clip "08_transition_ai"       19.5  0.5
# 12-14s AI-Powered    → dừng trước cảnh chữ J (~25s)
cut_clip "09_ai_powered"          20.0  2.5
# 14-15s Social proof  → text card: dùng frame mờ từ AI (post overlay)
cut_clip "10_social_hold"         22.0  1.0
# 15-16s Pre-CTA
cut_clip "11_pre_cta"             42.5  1.0
# 16-20s End card + CTA
cut_clip "12_endcard_cta"         43.0  4.0

echo ""
echo "=== Bước 2: Ghép concat (rough cut ~20s) ==="

cat > "$CLIPS/concat_list.txt" <<EOF
file '$CLIPS/01_hook_logo_endcard.mp4'
file '$CLIPS/02_hook_boardroom.mp4'
file '$CLIPS/03_performance_sky.mp4'
file '$CLIPS/04_performance_room.mp4'
file '$CLIPS/05_transition_flash.mp4'
file '$CLIPS/06_crm_automation.mp4'
file '$CLIPS/07_services_hold.mp4'
file '$CLIPS/08_transition_ai.mp4'
file '$CLIPS/09_ai_powered.mp4'
file '$CLIPS/10_social_hold.mp4'
file '$CLIPS/11_pre_cta.mp4'
file '$CLIPS/12_endcard_cta.mp4'
EOF

ffmpeg -y -hide_banner -loglevel error \
  -f concat -safe 0 -i "$CLIPS/concat_list.txt" \
  -c copy \
  "$OUT/ptt_like_page_20s_rough.mp4"

echo ""
echo "=== Bước 3: Xuất bản Meta (re-encode, ≤12MB target) ==="

ffmpeg -y -hide_banner -loglevel error -stats \
  -i "$OUT/ptt_like_page_20s_rough.mp4" \
  -c:v libx264 -preset slow -crf 23 -maxrate 4M -bufsize 8M \
  -vf "fps=30" -pix_fmt yuv420p \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  -t 20 \
  "$OUT/ptt_like_page_20s_meta.mp4"

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/ptt_like_page_20s_meta.mp4")
SIZE=$(du -h "$OUT/ptt_like_page_20s_meta.mp4" | cut -f1)

echo ""
echo "✓ Clips:     $CLIPS/"
echo "✓ Rough cut: $OUT/ptt_like_page_20s_rough.mp4"
echo "✓ Meta export: $OUT/ptt_like_page_20s_meta.mp4"
echo "  Duration: ${DUR}s | Size: ${SIZE}"
