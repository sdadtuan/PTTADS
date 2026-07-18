"""CMS image upload helpers: center crop (object-fit: cover) and WebP export."""
from __future__ import annotations

import io
from typing import Any

HERO_DESKTOP_PRESET = {"ratio_w": 16, "ratio_h": 9, "width": 1920}
HERO_MOBILE_PRESET = {"ratio_w": 9, "ratio_h": 16, "width": 1080}
HERO_MOBILE_VERSION = 2

PURPOSE_PRESETS: dict[str, dict[str, Any]] = {
    "hero": HERO_DESKTOP_PRESET,
    "hero_desktop": HERO_DESKTOP_PRESET,
    "hero_mobile": HERO_MOBILE_PRESET,
    "project": {"ratio_w": 3, "ratio_h": 2, "max_width": 1400},
    "news": {"ratio_w": 16, "ratio_h": 9, "max_width": 1200},
    "blog": {"ratio_w": 16, "ratio_h": 9, "max_width": 1200},
    "service": {"ratio_w": 16, "ratio_h": 9, "max_width": 1200},
}

CROPPABLE_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "webp"})
SKIP_EXTENSIONS = frozenset({"gif", "svg"})


def normalize_purpose(purpose: str | None) -> str | None:
    if not purpose:
        return None
    key = purpose.strip().lower()
    return key if key in PURPOSE_PRESETS else None


def _center_cover_crop(img, target_ratio: float):
    src_w, src_h = img.size
    if src_w <= 0 or src_h <= 0:
        return img
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        new_w = max(1, int(round(src_h * target_ratio)))
        left = (src_w - new_w) // 2
        box = (left, 0, left + new_w, src_h)
    else:
        new_h = max(1, int(round(src_w / target_ratio)))
        top = (src_h - new_h) // 2
        box = (0, top, src_w, top + new_h)
    return img.crop(box)


def _resize_max_width(img, max_width: int):
    w, h = img.size
    if w <= max_width:
        return img
    from PIL import Image

    new_h = max(1, int(round(h * max_width / w)))
    return img.resize((max_width, new_h), Image.Resampling.LANCZOS)


def _to_rgb(img):
    if img.mode in ("RGBA", "P"):
        return img.convert("RGB")
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def _encode_webp(img, *, quality: int = 82) -> tuple[bytes, int, int]:
    img = _to_rgb(img)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=quality, method=4)
    return buf.getvalue(), img.width, img.height


def _is_border_pixel(r: int, g: int, b: int, *, light: bool = True) -> bool:
    if light:
        return r >= 232 and g >= 232 and b >= 232
    return r <= 24 and g <= 24 and b <= 24


def _trim_letterbox(img, *, max_frac: float = 0.22):
    """Remove uniform white/black bars often baked into uploaded screenshots."""
    rgb = _to_rgb(img)
    w, h = rgb.size
    if w < 8 or h < 8:
        return rgb
    px = rgb.load()
    max_x = max(1, int(w * max_frac))
    max_y = max(1, int(h * max_frac))

    def row_is_border(y: int, *, light: bool) -> bool:
        hits = sum(1 for x in range(w) if _is_border_pixel(*px[x, y], light=light))
        return hits >= int(w * 0.94)

    def col_is_border(x: int, *, light: bool) -> bool:
        hits = sum(1 for y in range(h) if _is_border_pixel(*px[x, y], light=light))
        return hits >= int(h * 0.94)

    top = 0
    while top < max_y and (row_is_border(top, light=True) or row_is_border(top, light=False)):
        top += 1
    bottom = 0
    while bottom < max_y and (row_is_border(h - 1 - bottom, light=True) or row_is_border(h - 1 - bottom, light=False)):
        bottom += 1
    left = 0
    while left < max_x and (col_is_border(left, light=True) or col_is_border(left, light=False)):
        left += 1
    right = 0
    while right < max_x and (col_is_border(w - 1 - right, light=True) or col_is_border(w - 1 - right, light=False)):
        right += 1

    if top + bottom + 2 >= h or left + right + 2 >= w:
        return rgb
    return rgb.crop((left, top, w - right, h - bottom))


def _apply_preset(img, preset: dict[str, Any]):
    ratio = preset["ratio_w"] / preset["ratio_h"]
    out = _center_cover_crop(img, ratio)
    if preset.get("width"):
        target_w = int(preset["width"])
        target_h = max(1, int(round(target_w * preset["ratio_h"] / preset["ratio_w"])))
        from PIL import Image

        return out.resize((target_w, target_h), Image.Resampling.LANCZOS)
    return _resize_max_width(out, preset["max_width"])


def _prepare_image(img):
    return _trim_letterbox(img)


def edge_letterbox_ratio(img, *, band_frac: float = 0.05) -> float:
    """Share of edge-band pixels that look like empty letterbox (white/black bars)."""
    rgb = _to_rgb(img)
    w, h = rgb.size
    if w < 4 or h < 4:
        return 0.0
    px = rgb.load()
    band_y = max(1, int(h * band_frac))
    band_x = max(1, int(w * band_frac))
    edge_pixels: list[tuple[int, int, int]] = []
    for y in range(band_y):
        for x in range(w):
            edge_pixels.append(px[x, y])
            edge_pixels.append(px[x, h - 1 - y])
    for x in range(band_x):
        for y in range(h):
            edge_pixels.append(px[x, y])
            edge_pixels.append(px[w - 1 - x, y])
    if not edge_pixels:
        return 0.0
    borderish = sum(
        1
        for r, g, b in edge_pixels
        if _is_border_pixel(r, g, b, light=True) or _is_border_pixel(r, g, b, light=False)
    )
    return borderish / len(edge_pixels)


def write_hero_upload_files(
    upload_dir,
    desktop_bytes: bytes,
    mobile_bytes: bytes,
    *,
    base: str | None = None,
) -> dict[str, str]:
    """Persist hero desktop + mobile pair; return url paths."""
    from pathlib import Path
    import uuid

    root = Path(upload_dir)
    stem = base or uuid.uuid4().hex
    desktop_name = f"{stem}.webp"
    mobile_name = f"{stem}-mobile.webp"
    (root / desktop_name).write_bytes(desktop_bytes)
    (root / mobile_name).write_bytes(mobile_bytes)
    _hero_mobile_marker(root, stem).write_text("ok", encoding="utf-8")
    return {
        "url": f"/static/uploads/{desktop_name}",
        "url_mobile": f"/static/uploads/{mobile_name}",
        "filename": desktop_name,
        "filename_mobile": mobile_name,
    }


def _load_image(data: bytes, ext: str):
    from PIL import Image, ImageOps

    if ext.lower() in SKIP_EXTENSIONS or ext.lower() not in CROPPABLE_EXTENSIONS:
        return None
    img = Image.open(io.BytesIO(data))
    return ImageOps.exif_transpose(img)


def process_hero_variants(
    data: bytes,
    ext: str,
    *,
    quality: int = 82,
) -> tuple[bytes, bytes, dict[str, Any]] | None:
    """Return desktop + mobile WebP bytes for hero uploads."""
    img = _load_image(data, ext)
    if img is None:
        return None
    img = _prepare_image(img)
    desktop_img = _apply_preset(img, HERO_DESKTOP_PRESET)
    mobile_img = _apply_preset(img, HERO_MOBILE_PRESET)
    desktop_bytes, dw, dh = _encode_webp(desktop_img, quality=quality)
    mobile_bytes, mw, mh = _encode_webp(mobile_img, quality=quality)
    meta = {
        "cropped": True,
        "purpose": "hero",
        "width": dw,
        "height": dh,
        "width_mobile": mw,
        "height_mobile": mh,
    }
    return desktop_bytes, mobile_bytes, meta


def process_image_upload(
    data: bytes,
    ext: str,
    purpose: str | None,
    *,
    quality: int = 82,
) -> tuple[bytes, str, dict[str, Any]]:
    """Return processed bytes, output extension, and metadata."""
    meta: dict[str, Any] = {}
    ext = ext.lower()
    purpose_key = normalize_purpose(purpose)

    if ext in SKIP_EXTENSIONS:
        return data, ext, meta

    if ext not in CROPPABLE_EXTENSIONS:
        return data, ext, meta

    try:
        from PIL import Image, ImageOps
    except ImportError:
        return data, ext, meta

    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        if purpose_key in ("hero", "hero_desktop", "hero_mobile"):
            img = _prepare_image(img)

        if purpose_key:
            preset = PURPOSE_PRESETS[purpose_key]
            img = _apply_preset(img, preset)
            meta["cropped"] = True
            meta["purpose"] = purpose_key

        if ext in ("jpg", "jpeg", "png", "webp") or purpose_key:
            out_bytes, meta["width"], meta["height"] = _encode_webp(img, quality=quality)
            return out_bytes, "webp", meta

        return data, ext, meta
    except Exception:
        return data, ext, meta


def _uploads_filename(image_url: str) -> str | None:
    url = (image_url or "").strip()
    if not url.startswith("/static/uploads/"):
        return None
    name = url.rsplit("/", 1)[-1]
    return name or None


def resolve_hero_mobile_url(image_url: str, upload_dir) -> str:
    """Return mobile hero URL if a sibling *-mobile.webp already exists."""
    name = _uploads_filename(image_url)
    if not name or not name.endswith(".webp") or name.endswith("-mobile.webp"):
        return ""
    mobile_name = f"{name[:-5]}-mobile.webp"
    if (upload_dir / mobile_name).is_file():
        return f"/static/uploads/{mobile_name}"
    return ""


def _hero_mobile_marker(upload_dir, stem: str) -> "Path":
    from pathlib import Path

    return Path(upload_dir) / f"{stem}-mobile.v{HERO_MOBILE_VERSION}"


def ensure_hero_mobile_url(image_url: str, upload_dir) -> str:
    """Resolve or generate a 9:16 mobile hero variant for local uploads."""
    name = _uploads_filename(image_url)
    if not name:
        return ""
    src = upload_dir / name
    if not src.is_file():
        return ""
    mobile_name = f"{src.stem}-mobile.webp"
    mobile_path = upload_dir / mobile_name
    marker = _hero_mobile_marker(upload_dir, src.stem)
    if mobile_path.is_file() and marker.is_file():
        return f"/static/uploads/{mobile_name}"
    ext = src.suffix.lstrip(".").lower()
    if ext not in CROPPABLE_EXTENSIONS:
        return ""
    try:
        data = src.read_bytes()
        img = _load_image(data, ext)
        if img is None:
            return ""
        img = _prepare_image(img)
        mobile_img = _apply_preset(img, HERO_MOBILE_PRESET)
        mobile_bytes, _, _ = _encode_webp(mobile_img)
        mobile_path.write_bytes(mobile_bytes)
        marker.write_text("ok", encoding="utf-8")
        return f"/static/uploads/{mobile_name}"
    except Exception:
        return ""


def normalize_hero_slides(slides: list, upload_dir) -> list:
    """Clear stale mobile hero URLs when the file is missing on disk."""
    if not isinstance(slides, list):
        return slides
    out: list[dict[str, Any]] = []
    for item in slides:
        if not isinstance(item, dict):
            continue
        slide = dict(item)
        image_url = str(slide.get("image_url") or "").strip()
        mobile_url = str(slide.get("image_url_mobile") or "").strip()
        if image_url and mobile_url:
            mobile_name = mobile_url.rsplit("/", 1)[-1]
            if not (upload_dir / mobile_name).is_file():
                slide["image_url_mobile"] = ""
        out.append(slide)
    return out or slides
