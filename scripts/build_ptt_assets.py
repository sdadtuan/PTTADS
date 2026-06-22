#!/usr/bin/env python3
"""
Nén raster trong PTT/static/ sang WebP và minify styles.css / *.js sang *.min.*

  cd PTT && python3 scripts/build_ptt_assets.py

Yêu cầu: pip install pillow rcssmin rjsmin
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
RASTER_SUFFIX = frozenset({".jpg", ".jpeg", ".png", ".bmp"})


def _min_css_js() -> int:
    try:
        import rcssmin  # type: ignore[import-untyped]
        import rjsmin  # type: ignore[import-untyped]
    except ImportError:
        print("Thiếu package: pip install rcssmin rjsmin", file=sys.stderr)
        raise SystemExit(1) from None

    n = 0
    css = STATIC / "styles.css"
    if css.is_file():
        out = STATIC / "styles.min.css"
        out.write_text(rcssmin.cssmin(css.read_text(encoding="utf-8")), encoding="utf-8")
        n += 1
        print("OK:", out.relative_to(ROOT))

    for js in sorted(STATIC.glob("*.js")):
        if js.name.endswith(".min.js"):
            continue
        dst = js.with_name(js.stem + ".min.js")
        dst.write_text(rjsmin.jsmin(js.read_text(encoding="utf-8")), encoding="utf-8")
        n += 1
        print("OK:", dst.relative_to(ROOT))
    return n


def _webp_rasters() -> int:
    try:
        from PIL import Image
    except ImportError:
        print("(bỏ qua WebP) Cài Pillow: pip install pillow", file=sys.stderr)
        return 0

    count = 0
    if not STATIC.is_dir():
        return 0
    for src in STATIC.rglob("*"):
        if not src.is_file() or src.suffix.lower() not in RASTER_SUFFIX:
            continue
        dst = src.with_suffix(".webp")
        if dst.is_file() and dst.stat().st_mtime >= src.stat().st_mtime:
            continue
        im = Image.open(src)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
        im.save(dst, "WEBP", quality=82, method=6)
        count += 1
        print("WebP:", dst.relative_to(ROOT))
    return count


def main() -> int:
    if not STATIC.is_dir():
        print(f"Không thấy thư mục {STATIC}", file=sys.stderr)
        return 1

    nm = _min_css_js()
    print(f"Đã minify {nm} file CSS/JS.")

    nw = _webp_rasters()
    if nw:
        print(f"Đã tạo/cập nhật {nw} ảnh WebP.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
