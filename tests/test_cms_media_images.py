# tests/test_cms_media_images.py
"""Tests for CMS image cover-crop on upload."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from cms_media_images import (
    edge_letterbox_ratio,
    ensure_hero_mobile_url,
    normalize_hero_slides,
    normalize_purpose,
    process_hero_variants,
    process_image_upload,
    resolve_hero_mobile_url,
    write_hero_upload_files,
)


def _make_image_bytes(width: int, height: int, color=(120, 180, 60)):
    from PIL import Image

    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _make_letterbox_image_bytes(width: int = 1920, height: int = 1080):
    from PIL import Image

    im = Image.new("RGB", (width, height), (255, 255, 255))
    core = Image.new("RGB", (int(width * 0.82), int(height * 0.72)), (40, 120, 60))
    im.paste(core, ((width - core.width) // 2, (height - core.height) // 2))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return buf.getvalue()


class CmsMediaImagesTests(unittest.TestCase):
    def test_normalize_purpose(self):
        self.assertEqual(normalize_purpose("hero"), "hero")
        self.assertEqual(normalize_purpose("hero_desktop"), "hero_desktop")
        self.assertEqual(normalize_purpose("hero_mobile"), "hero_mobile")
        self.assertEqual(normalize_purpose(" HERO "), "hero")
        self.assertIsNone(normalize_purpose("unknown"))
        self.assertIsNone(normalize_purpose(""))

    def test_hero_desktop_preset(self):
        data = _make_image_bytes(1600, 1200)
        out, ext, meta = process_image_upload(data, "jpg", "hero_desktop")
        self.assertEqual(ext, "webp")
        self.assertTrue(meta.get("cropped"))
        self.assertEqual(meta.get("purpose"), "hero_desktop")
        self.assertAlmostEqual(meta["width"] / meta["height"], 16 / 9, places=2)
        self.assertEqual(meta["width"], 1920)

    def test_hero_mobile_preset(self):
        data = _make_image_bytes(1200, 2000)
        out, ext, meta = process_image_upload(data, "jpg", "hero_mobile")
        self.assertEqual(ext, "webp")
        self.assertTrue(meta.get("cropped"))
        self.assertEqual(meta.get("purpose"), "hero_mobile")
        self.assertAlmostEqual(meta["width"] / meta["height"], 9 / 16, places=2)
        self.assertEqual(meta["width"], 1080)
        self.assertEqual(meta["height"], 1920)

    def test_hero_cover_crops_landscape_letterbox(self):
        # Wide image with extra height (4:3 in 16:9 frame feel)
        data = _make_image_bytes(1600, 1200)
        out, ext, meta = process_image_upload(data, "jpg", "hero")
        self.assertEqual(ext, "webp")
        self.assertTrue(meta.get("cropped"))
        self.assertEqual(meta.get("purpose"), "hero")
        self.assertAlmostEqual(meta["width"] / meta["height"], 16 / 9, places=2)
        self.assertEqual(meta["width"], 1920)
        self.assertEqual(meta["height"], 1080)

    def test_hero_cover_crops_portrait(self):
        data = _make_image_bytes(900, 1600)
        out, ext, meta = process_image_upload(data, "png", "hero")
        self.assertEqual(ext, "webp")
        self.assertTrue(meta.get("cropped"))
        self.assertAlmostEqual(meta["width"] / meta["height"], 16 / 9, places=2)

    def test_no_purpose_only_converts_to_webp(self):
        data = _make_image_bytes(800, 600)
        out, ext, meta = process_image_upload(data, "jpg", None)
        self.assertEqual(ext, "webp")
        self.assertNotIn("cropped", meta)
        self.assertEqual(meta["width"], 800)
        self.assertEqual(meta["height"], 600)

    def test_project_preset_uses_three_two_ratio(self):
        data = _make_image_bytes(1200, 1200)
        _, ext, meta = process_image_upload(data, "jpg", "project")
        self.assertEqual(ext, "webp")
        self.assertAlmostEqual(meta["width"] / meta["height"], 3 / 2, places=2)


    def test_hero_variants_return_desktop_and_mobile(self):
        data = _make_image_bytes(1600, 1200)
        result = process_hero_variants(data, "jpg")
        self.assertIsNotNone(result)
        desktop, mobile, meta = result
        self.assertGreater(len(desktop), 100)
        self.assertGreater(len(mobile), 100)
        self.assertAlmostEqual(meta["width"] / meta["height"], 16 / 9, places=2)
        self.assertAlmostEqual(meta["width_mobile"] / meta["height_mobile"], 9 / 16, places=2)
        self.assertEqual(meta["width_mobile"], 1080)
        self.assertEqual(meta["height_mobile"], 1920)

    def test_trim_letterbox_removes_white_bars(self):
        from cms_media_images import _trim_letterbox
        from PIL import Image

        im = Image.new("RGB", (400, 300), (255, 255, 255))
        core = Image.new("RGB", (360, 220), (40, 120, 60))
        im.paste(core, (20, 40))
        trimmed = _trim_letterbox(im)
        self.assertLess(trimmed.size[1], im.size[1])
        self.assertLess(trimmed.size[0], im.size[0])

    def test_hero_upload_desktop_and_mobile_both_full(self):
        """Upload hero: desktop 16:9 và mobile 9:16 đều không còn viền trắng."""
        from PIL import Image

        data = _make_letterbox_image_bytes(1920, 1080)
        result = process_hero_variants(data, "jpg")
        self.assertIsNotNone(result)
        desktop_bytes, mobile_bytes, meta = result
        desktop_im = Image.open(io.BytesIO(desktop_bytes))
        mobile_im = Image.open(io.BytesIO(mobile_bytes))
        self.assertLess(edge_letterbox_ratio(desktop_im), 0.04)
        self.assertLess(edge_letterbox_ratio(mobile_im), 0.04)
        self.assertAlmostEqual(meta["width"] / meta["height"], 16 / 9, places=2)
        self.assertAlmostEqual(meta["width_mobile"] / meta["height_mobile"], 9 / 16, places=2)

    def test_write_hero_upload_files_creates_pair_and_marker(self):
        data = _make_image_bytes(1400, 900)
        desktop, mobile, _ = process_hero_variants(data, "jpg")
        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            paths = write_hero_upload_files(upload_dir, desktop, mobile, base="testhero")
            self.assertTrue((upload_dir / "testhero.webp").is_file())
            self.assertTrue((upload_dir / "testhero-mobile.webp").is_file())
            self.assertTrue((upload_dir / "testhero-mobile.v2").is_file())
            self.assertEqual(paths["url_mobile"], "/static/uploads/testhero-mobile.webp")

    def test_ensure_hero_mobile_generates_sibling_file(self):
        data = _make_image_bytes(1400, 900)
        desktop, mobile, _ = process_hero_variants(data, "jpg")
        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            desktop_name = "abc123.webp"
            (upload_dir / desktop_name).write_bytes(desktop)
            url = f"/static/uploads/{desktop_name}"
            self.assertEqual(resolve_hero_mobile_url(url, upload_dir), "")
            mobile_url = ensure_hero_mobile_url(url, upload_dir)
            self.assertTrue(mobile_url.endswith("-mobile.webp"))
            self.assertTrue((upload_dir / "abc123-mobile.webp").is_file())

    def test_normalize_hero_slides_does_not_auto_generate_mobile(self):
        data = _make_image_bytes(1400, 900)
        desktop, _, _ = process_hero_variants(data, "jpg")
        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            desktop_name = "abc123.webp"
            (upload_dir / desktop_name).write_bytes(desktop)
            url = f"/static/uploads/{desktop_name}"
            slides = normalize_hero_slides([{"image_url": url}], upload_dir)
            self.assertEqual(slides[0].get("image_url_mobile", ""), "")

    def test_normalize_hero_slides_clears_missing_mobile_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            url = "/static/uploads/abc123.webp"
            (upload_dir / "abc123.webp").write_bytes(b"x")
            slides = normalize_hero_slides(
                [{"image_url": url, "image_url_mobile": "/static/uploads/missing-mobile.webp"}],
                upload_dir,
            )
            self.assertEqual(slides[0]["image_url_mobile"], "")


if __name__ == "__main__":
    unittest.main()
