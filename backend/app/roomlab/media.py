"""Bounded video container validation, duration probing, and timestamped frame extraction for RoomLab.

Uses the bundled imageio_ffmpeg binary to decode real video streams without relying on
browser-reported duration or legacy board-specific helpers.
"""
from __future__ import annotations

import hashlib
import math
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import uuid
from typing import Literal

import imageio_ffmpeg
from PIL import Image

from backend.app.roomlab.contracts import EvidenceFrame, MediaRecord

MAX_MEDIA_BYTES = 1024 * 1024 * 1024
MAX_DURATION_S = 600.0
MIN_DURATION_S = 0.05
MAX_FRAMES = 200
TARGET_FRAME_WIDTH = 960

AllowedMime = Literal["video/mp4", "video/webm", "video/quicktime"]

EXT_FOR_MIME: dict[AllowedMime, str] = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(filename: str, default_ext: str) -> str:
    raw = os.path.basename((filename or "").strip())
    cleaned = _SAFE_FILENAME_RE.sub("_", raw).strip("._")
    if not cleaned:
        return f"source{default_ext}"
    if len(cleaned) > 120:
        cleaned = cleaned[:120]
    return cleaned


def _detect_container_mime(data: bytes, declared_mime: str, filename: str) -> AllowedMime:
    """Inspect magic bytes first; reject non-video or mismatched containers."""
    if len(data) < 12:
        raise ValueError("Uploaded media file is too small or empty.")

    # EBML / WebM / Matroska magic: 0x1A 0x45 0xDF 0xA3
    if data[:4] == b"\x1a\x45\xdf\xa3":
        header_window = data[:4096].lower()
        if (
            b"webm" in header_window
            or (declared_mime or "").lower() == "video/webm"
            or (filename or "").lower().endswith(".webm")
        ):
            return "video/webm"
        raise ValueError("Unsupported Matroska container; upload MP4, WebM, or QuickTime MOV.")

    # ISO BMFF / MP4 / QuickTime: bytes 4..8 == b'ftyp' or moov/mdat/wide
    box_type = data[4:8]
    if box_type in (b"ftyp", b"moov", b"wide", b"mdat", b"free", b"skip"):
        if box_type == b"ftyp":
            brand = data[8:12]
            if brand == b"qt  ":
                return "video/quicktime"
            return "video/mp4"
        ext = os.path.splitext((filename or "").lower())[1]
        if ext == ".mov" or (declared_mime or "").lower() == "video/quicktime":
            return "video/quicktime"
        return "video/mp4"

    raise ValueError("Unsupported media format. Please upload an MP4, WebM, or QuickTime (.mov) video.")


def _parse_ffmpeg_duration(stderr_text: str) -> float | None:
    """Parse duration from ffmpeg stderr (either final muxing time= or header Duration:)."""
    time_matches = re.findall(r"time=\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr_text)
    if time_matches:
        hh, mm, ss = time_matches[-1]
        val = int(hh) * 3600 + int(mm) * 60 + float(ss)
        if val > 0:
            return val

    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr_text)
    if dur_match:
        hh, mm, ss = dur_match.groups()
        val = int(hh) * 3600 + int(mm) * 60 + float(ss)
        if val > 0:
            return val
    return None


def _probe_and_measure_duration(ffmpeg_exe: str, video_path: pathlib.Path) -> float:
    """Decode stream to null sink to measure actual playable duration and verify video stream."""
    cmd = [
        ffmpeg_exe,
        "-hide_banner",
        "-nostdin",
        "-v",
        "info",
        "-i",
        str(video_path),
        "-map",
        "0:v:0",
        "-an",
        "-f",
        "null",
        "-",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Video inspection timed out.") from exc

    stderr = proc.stderr or ""
    if proc.returncode != 0 or "Video:" not in stderr:
        raise ValueError("Uploaded file could not be decoded as a valid video stream.")

    duration = _parse_ffmpeg_duration(stderr)
    if duration is None or duration <= 0:
        frame_matches = re.findall(r"frame=\s*(\d+)", stderr)
        fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", stderr)
        if frame_matches and int(frame_matches[-1]) > 0:
            frames = int(frame_matches[-1])
            fps = float(fps_match.group(1)) if fps_match else 10.0
            duration = max(MIN_DURATION_S, frames / max(fps, 1.0))
        else:
            raise ValueError("Could not determine a valid positive duration for the uploaded video.")

    if duration > MAX_DURATION_S + 0.25:
        raise ValueError(
            f"Video duration ({duration:.2f}s) exceeds the {MAX_DURATION_S:.0f}s maximum limit."
        )
    return round(min(max(duration, MIN_DURATION_S), MAX_DURATION_S), 3)


def _select_timestamps(duration_s: float, max_frames: int = MAX_FRAMES) -> list[float]:
    if duration_s <= 0.4:
        return [0.0]
    if duration_s <= 16.0:
        count = min(max_frames, max(2, int(round(duration_s * 1.25)) + 1))
    elif duration_s <= 120:
        count = min(max_frames, 48, max(16, int(round(duration_s * 0.6)) + 1))
    else:
        count = min(max_frames, max(48, math.ceil(duration_s / 2.5) + 1))
    span = max(0.0, duration_s - 0.08)
    if count == 1 or span <= 0:
        return [0.0]
    step = span / (count - 1)
    return [round(i * step, 3) for i in range(count)]


def _extract_frame_jpeg(
    ffmpeg_exe: str,
    video_path: pathlib.Path,
    timestamp_s: float,
    output_path: pathlib.Path,
) -> bool:
    cmd = [
        ffmpeg_exe,
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-ss",
        f"{timestamp_s:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "3",
        "-y",
        str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
    if proc.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        return False

    try:
        with Image.open(output_path) as img:
            img.load()
            w, h = img.size
            if w <= 0 or h <= 0:
                return False
            if max(w, h) > TARGET_FRAME_WIDTH:
                scale = TARGET_FRAME_WIDTH / float(max(w, h))
                resized = img.convert("RGB").resize(
                    (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
                    Image.Resampling.LANCZOS,
                )
                resized.save(output_path, format="JPEG", quality=85)
    except Exception:
        return False
    return True


def process_media(
    data: bytes,
    filename: str,
    mime_type: str,
    media_root: pathlib.Path,
) -> MediaRecord:
    """Validate uploaded video bytes, persist under media_root/media_id, and extract <=200 JPEG frames."""
    if not isinstance(data, (bytes, bytearray)) or len(data) == 0:
        raise ValueError("Uploaded video file is empty.")
    if len(data) > MAX_MEDIA_BYTES:
        raise ValueError(
            f"Uploaded video ({len(data) / (1024 * 1024):.1f} MiB) exceeds the 1024 MiB limit."
        )

    detected_mime = _detect_container_mime(bytes(data), mime_type or "", filename or "")
    declared = (mime_type or "").split(";")[0].strip().lower()
    if declared and declared not in ("application/octet-stream", "video/*", ""):
        if declared not in EXT_FOR_MIME:
            raise ValueError(f"Unsupported MIME type '{declared}'. Allowed: video/mp4, video/webm, video/quicktime.")
        if (declared == "video/webm") != (detected_mime == "video/webm"):
            raise ValueError(f"Container format ({detected_mime}) does not match declared MIME type ({declared}).")

    ext = EXT_FOR_MIME[detected_mime]
    safe_name = _sanitize_filename(filename or f"source{ext}", ext)
    digest = hashlib.sha256(data).hexdigest()[:10]
    media_id = f"media-{digest}-{uuid.uuid4().hex[:6]}"

    media_root = pathlib.Path(media_root).resolve()
    media_root.mkdir(parents=True, exist_ok=True)
    target_dir = (media_root / media_id).resolve()
    if target_dir.parent != media_root:
        raise ValueError("Invalid media directory resolution.")

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    with tempfile.TemporaryDirectory(prefix="roomlab_media_") as tmp_dir_str:
        tmp_dir = pathlib.Path(tmp_dir_str)
        source_name = f"source{ext}"
        tmp_video = tmp_dir / source_name
        tmp_video.write_bytes(data)

        duration_s = _probe_and_measure_duration(ffmpeg_exe, tmp_video)
        timestamps = _select_timestamps(duration_s, MAX_FRAMES)

        extracted: list[tuple[int, float, pathlib.Path]] = []
        for idx, ts in enumerate(timestamps, start=1):
            frame_file = tmp_dir / f"frame-{idx:03d}.jpg"
            ok = _extract_frame_jpeg(ffmpeg_exe, tmp_video, ts, frame_file)
            if not ok and idx == 1:
                ok = _extract_frame_jpeg(ffmpeg_exe, tmp_video, 0.0, frame_file)
            if ok:
                extracted.append((idx, ts, frame_file))

        if not extracted:
            raise ValueError("Failed to decode any video frames from the uploaded clip.")

        target_dir.mkdir(parents=True, exist_ok=True)
        final_video_path = target_dir / source_name
        shutil.move(str(tmp_video), str(final_video_path))

        frames: list[EvidenceFrame] = []
        for out_idx, (_, ts, temp_frame) in enumerate(extracted[:MAX_FRAMES], start=1):
            fname = f"frame-{out_idx:03d}.jpg"
            dest_frame = target_dir / fname
            shutil.move(str(temp_frame), str(dest_frame))
            rel_path = f"{media_id}/{fname}"
            frames.append(
                EvidenceFrame(
                    frame_id=f"{media_id}-frame-{out_idx:03d}",
                    media_id=media_id,
                    timestamp_s=round(min(ts, duration_s), 3),
                    url=f"/media/{rel_path}",
                    relative_path=rel_path,
                )
            )

    return MediaRecord(
        media_id=media_id,
        filename=safe_name,
        mime_type=detected_mime,
        duration_s=duration_s,
        video_url=f"/media/{media_id}/{source_name}",
        frames=frames,
    )
