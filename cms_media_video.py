"""CMS video upload helpers: compress hero clips for fast progressive playback."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

HERO_VIDEO_MAX_WIDTH = 1920
HERO_VIDEO_MAX_HEIGHT = 1080
HERO_VIDEO_CRF = 28
HERO_VIDEO_PRESET = "fast"

VIDEO_EXTENSIONS = frozenset({"mp4", "webm", "mov"})


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def process_video_upload(
    data: bytes,
    ext: str,
    purpose: str | None = None,
) -> tuple[bytes, str, dict[str, Any]] | None:
    """Return optimized MP4 bytes, extension, and metadata. None → keep original."""
    ext = ext.lower()
    if ext not in VIDEO_EXTENSIONS:
        return None
    if not _ffmpeg_available():
        return None

    _ = purpose  # reserved for future presets (e.g. inline vs hero)

    input_suffix = f".{ext}"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        src = tmp_dir / f"in{input_suffix}"
        dst = tmp_dir / "out.mp4"
        src.write_bytes(data)

        scale = (
            f"scale='min({HERO_VIDEO_MAX_WIDTH},iw)':"
            f"'min({HERO_VIDEO_MAX_HEIGHT},ih)':"
            "force_original_aspect_ratio=decrease,"
            "scale=trunc(iw/2)*2:trunc(ih/2)*2"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-an",
            "-vf",
            scale,
            "-c:v",
            "libx264",
            "-preset",
            HERO_VIDEO_PRESET,
            "-crf",
            str(HERO_VIDEO_CRF),
            "-movflags",
            "+faststart",
            "-pix_fmt",
            "yuv420p",
            "-max_muxing_queue_size",
            "4096",
            str(dst),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return None

        if not dst.is_file() or dst.stat().st_size <= 0:
            return None

        out_bytes = dst.read_bytes()
        if len(out_bytes) >= len(data):
            return None

        meta: dict[str, Any] = {
            "optimized": True,
            "video_codec": "h264",
            "size_before": len(data),
            "width": HERO_VIDEO_MAX_WIDTH,
        }
        try:
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height",
                    "-of",
                    "csv=p=0",
                    str(dst),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            parts = probe.stdout.strip().split(",")
            if len(parts) >= 2:
                meta["width"] = int(parts[0])
                meta["height"] = int(parts[1])
        except (subprocess.CalledProcessError, ValueError, OSError):
            pass

        return out_bytes, "mp4", meta
