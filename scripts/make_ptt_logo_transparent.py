"""
Gỡ nền đặc quanh logo PTT (PNG) theo màu viền + feather viền.
Chạy:  python scripts/make_ptt_logo_transparent.py
"""
import math
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "static" / "images" / "ptt-logo.png"
T_HARD = 38
T_SOFT = 72


def main() -> None:
    im = Image.open(LOGO).convert("RGBA")
    w, h = im.size
    px = im.load()
    border: list[tuple[int, int, int]] = []
    for x in range(w):
        for y in (0, h - 1, max(1, h // 2)):
            border.append(px[x, y][:3])
    for y in range(h):
        for x in (0, w - 1, max(1, w // 2)):
            border.append(px[x, y][:3])
    bg = Counter(border).most_common(1)[0][0]
    print("Border mode RGB:", bg)
    out: list[tuple[int, int, int, int]] = []
    for y in range(h):
        for x in range(w):
            r, g, b, _a = px[x, y]
            d = math.sqrt((r - bg[0]) ** 2 + (g - bg[1]) ** 2 + (b - bg[2]) ** 2)
            if d <= T_HARD:
                a = 0
            elif d >= T_SOFT:
                a = 255
            else:
                t = (d - T_HARD) / (T_SOFT - T_HARD)
                a = int(255 * t)
                if a < 8:
                    a = 0
            out.append((r, g, b, a))
    out_img = Image.new("RGBA", (w, h))
    out_img.putdata(out)
    out_img.save(LOGO, optimize=True)
    print("Saved:", LOGO)


if __name__ == "__main__":
    main()
