# tests/test_cms_media_video.py
"""Tests for CMS hero video optimization on upload."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cms_media_video import _ffmpeg_available, process_video_upload


def _make_test_video_bytes(duration: float = 1.0) -> bytes:
    if not _ffmpeg_available():
        raise unittest.SkipTest("ffmpeg not available")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "clip.mov"
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=green:s=2560x1440:d={duration}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        return out.read_bytes()


class CmsMediaVideoTests(unittest.TestCase):
    def test_process_video_upload_optimizes_large_clip(self):
        if not _ffmpeg_available():
            self.skipTest("ffmpeg not available")
        raw = _make_test_video_bytes()
        result = process_video_upload(raw, "mov", "hero_video")
        self.assertIsNotNone(result)
        out_bytes, ext, meta = result
        self.assertEqual(ext, "mp4")
        self.assertTrue(meta.get("optimized"))
        self.assertLess(len(out_bytes), len(raw))
        self.assertLessEqual(meta.get("width", 9999), 1920)
        self.assertLessEqual(meta.get("height", 9999), 1080)

    def test_process_video_upload_unknown_ext_returns_none(self):
        result = process_video_upload(b"not-a-video", "txt", None)
        self.assertIsNone(result)

    def test_ffmpeg_available_matches_which(self):
        self.assertEqual(_ffmpeg_available(), shutil.which("ffmpeg") is not None)


if __name__ == "__main__":
    unittest.main()
