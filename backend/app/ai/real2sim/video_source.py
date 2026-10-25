"""Video walkthrough sources for Real2Sim: container check, measured duration, and a compact copy for Argon.

A phone walkthrough (MP4, WebM or MOV, at most 120 s and 256 MB) is decoded with ffmpeg: the duration is measured from
the stream, never taken from the browser, and the clip is re-encoded once to a small silent H.264 MP4 (at most 640 px
wide, a few frames per second) so it fits in one inline request part. Argon samples video at about one frame per second,
so the lower frame rate loses nothing it would read.

Coordinates of a video draft refer to a square top-down plan canvas (``PLAN_CANVAS_PX``), not to any frame: Argon lays
the space out as a plan. The overlay is therefore drawn on a blank canvas, as for a PDF.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from backend.app.ai.real2sim.drafts import Real2SimError
from backend.app.ai.real2sim.extract import SourceDocument
from backend.app.ai.real2sim.schema import SourceImage

MAX_VIDEO_BYTES = 256 * 1024 * 1024
MAX_DURATION_S = 120.0
MIN_DURATION_S = 1.0
MAX_INLINE_BYTES = 18 * 1024 * 1024          # one inline part; the request limit is about 20 MB
PLAN_CANVAS_PX = 1000
VIDEO_MIME = "video/mp4"
# Encoder passes, smallest last: (max width px, frames per second, x264 CRF).
_PASSES = ((640, 4, 30), (480, 2, 34), (360, 1, 38))
_FFMPEG_TIMEOUT_S = 240
_TIME = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


def detect_container(head: bytes) -> str:
    """The container from its magic bytes: ``video/mp4``, ``video/quicktime`` or ``video/webm``."""
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "video/quicktime" if head[8:12] == b"qt  " else "video/mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    raise Real2SimError("unsupported_mime_type", 415)


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        found = shutil.which("ffmpeg")
        if found:
            return found
    raise Real2SimError("video_decoder_unavailable", 503)


def _run(args: List[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, capture_output=True, timeout=_FFMPEG_TIMEOUT_S, check=False)
    except subprocess.TimeoutExpired:
        raise Real2SimError("video_processing_timeout", 422) from None
    except OSError:
        raise Real2SimError("video_decoder_unavailable", 503) from None


def measure_duration(exe: str, path: Path) -> float:
    """Decode the whole video stream to a null sink; the last progress time is the playable duration."""
    done = _run([exe, "-hide_banner", "-nostdin", "-i", str(path), "-map", "0:v:0", "-f", "null", "-"])
    matches = _TIME.findall(done.stderr.decode("utf-8", "replace"))
    if done.returncode != 0 or not matches:
        raise Real2SimError("invalid_source_video", 422)
    hours, minutes, seconds = matches[-1]
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if duration <= 0:
        raise Real2SimError("invalid_source_video", 422)
    if duration > MAX_DURATION_S + 0.25:
        raise Real2SimError("video_too_long", 422, max_seconds=int(MAX_DURATION_S))
    if duration < MIN_DURATION_S:
        raise Real2SimError("video_too_short", 422, min_seconds=int(MIN_DURATION_S))
    return duration


def compact_copy(exe: str, path: Path, workdir: Path) -> Tuple[bytes, str]:
    """The smallest-effort pass that fits one inline part; returns the bytes and a plain description."""
    for index, (width, fps, crf) in enumerate(_PASSES):
        out = workdir / f"compact-{index}.mp4"
        done = _run([exe, "-hide_banner", "-nostdin", "-y", "-i", str(path), "-t", f"{MAX_DURATION_S:.0f}", "-an",
                     "-vf", f"scale='min({width},iw)':-2,fps={fps}", "-c:v", "libx264", "-preset", "veryfast",
                     "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)])
        if done.returncode != 0 or not out.is_file():
            raise Real2SimError("invalid_source_video", 422)
        data = out.read_bytes()
        if 0 < len(data) <= MAX_INLINE_BYTES:
            return data, f"re-encoded for reading: at most {width} px wide, {fps} frame{'s' if fps > 1 else ''}/s, no audio"
    raise Real2SimError("video_too_large_to_read", 413)


def prepare_video(path: Path, *, original_bytes: Optional[int] = None) -> Tuple[SourceDocument, List[str]]:
    """Validate an uploaded video file and return the source Argon reads plus plain-language notes."""
    with path.open("rb") as handle:
        head = handle.read(64)
    container = detect_container(head)
    size = original_bytes if original_bytes is not None else path.stat().st_size
    if size <= 0:
        raise Real2SimError("source_required", 422)
    if size > MAX_VIDEO_BYTES:
        raise Real2SimError("source_too_large", 413)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    exe = ffmpeg_exe()
    duration = measure_duration(exe, path)
    with tempfile.TemporaryDirectory(prefix="r2s-video-") as tmp:
        data, how = compact_copy(exe, path, Path(tmp))
    notes = [f"{container.split('/')[1].upper()} walkthrough, {duration:.0f} s", how,
             "laid out as a top-down plan; the overlay is drawn on a blank canvas"]
    image = SourceImage(PLAN_CANVAS_PX, PLAN_CANVAS_PX, digest.hexdigest(), VIDEO_MIME)
    return SourceDocument(data, VIDEO_MIME, "video", image, None), notes
