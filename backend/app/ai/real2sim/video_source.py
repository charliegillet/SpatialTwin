"""Video walkthrough sources for Real2Sim: container check, measured duration, keyframes, and the clip Argon reads.

A phone walkthrough (MP4, WebM or MOV, at most 120 s and 256 MB) is prepared the way the RoomLab branch prepares it
(``roomlab/media.py``): ffmpeg measures the duration from the stream (never the browser's figure) and extracts up to 48
timestamped keyframes (at most 960 px, JPEG). The clip itself goes inline when it is at most 20 MB; RoomLab then left the
clip out, while here a small silent H.264 copy (at most 640 px, a few frames per second) is sent instead, so Argon
still sees the motion between keyframes.

A video is read as one room in metres (``extract.DraftExtractor.read_room``), not on an image grid; ``PLAN_CANVAS_PX`` is
only the frame size recorded for the draft's evidence pictures.
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
MAX_INLINE_BYTES = 18 * 1024 * 1024          # the compact copy, when the original is over RoomLab's 20 MB inline limit
MAX_ORIGINAL_INLINE_BYTES = 20 * 1024 * 1024
MAX_FRAMES = 48                              # RoomLab's keyframe budget and timestamp schedule
TARGET_FRAME_PX = 960
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


def select_timestamps(duration_s: float, max_frames: int = MAX_FRAMES) -> List[float]:
    """RoomLab's keyframe schedule: about 1.25 per second for short clips, 0.6 per second (at least 16) after 16 s."""
    if duration_s <= 0.4:
        return [0.0]
    if duration_s <= 16.0:
        count = min(max_frames, max(2, int(round(duration_s * 1.25)) + 1))
    else:
        count = min(max_frames, max(16, int(round(duration_s * 0.6)) + 1))
    span = max(0.0, duration_s - 0.08)
    if count == 1 or span <= 0:
        return [0.0]
    step = span / (count - 1)
    return [round(i * step, 3) for i in range(count)]


def keyframes(exe: str, path: Path, duration_s: float, workdir: Path) -> List[Tuple[str, float, bytes]]:
    frames: List[Tuple[str, float, bytes]] = []
    for timestamp in select_timestamps(duration_s):
        out = workdir / f"frame-{len(frames) + 1:03d}.jpg"
        done = _run([exe, "-hide_banner", "-nostdin", "-loglevel", "error", "-ss", f"{timestamp:.3f}", "-i", str(path),
                     "-frames:v", "1", "-vf", f"scale='min({TARGET_FRAME_PX},iw)':'min({TARGET_FRAME_PX},ih)':"
                     "force_original_aspect_ratio=decrease", "-q:v", "3", "-y", str(out)])
        if done.returncode == 0 and out.is_file() and out.stat().st_size > 0:
            frames.append((f"frame-{len(frames) + 1:03d}", timestamp, out.read_bytes()))
    if not frames:
        raise Real2SimError("invalid_source_video", 422)
    return frames


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
    label = {"video/mp4": "MP4", "video/webm": "WebM", "video/quicktime": "MOV"}[container]
    with tempfile.TemporaryDirectory(prefix="r2s-video-") as tmp:
        frames = keyframes(exe, path, duration, Path(tmp))
        if size <= MAX_ORIGINAL_INLINE_BYTES:
            data, mime, how = path.read_bytes(), container, "the clip is read as uploaded"
        else:
            data, how = compact_copy(exe, path, Path(tmp))
            mime = VIDEO_MIME
    notes = [f"{label} walkthrough, {duration:.0f} s", f"{len(frames)} timestamped keyframes", how]
    image = SourceImage(PLAN_CANVAS_PX, PLAN_CANVAS_PX, digest.hexdigest(), mime)
    return SourceDocument(data, mime, "video", image, None, frames=tuple(frames), duration_s=round(duration, 3)), notes
