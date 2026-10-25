"""Video normalisation and frame extraction (ffmpeg/ffprobe wrappers)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

_BREW = "/opt/homebrew/bin"


def _bin(name: str) -> str:
    return shutil.which(name) or os.path.join(_BREW, name)


@dataclass(frozen=True)
class PreparedVideo:
    path: Path
    sha256: str
    duration_s: float
    width: int
    height: int


def _probe(path: Path) -> dict:
    out = subprocess.run(
        [_bin("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:format=duration",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def prepare_video(src: Path, out_dir: Path, max_s: float = 180) -> PreparedVideo:
    """Transcode to H.264 mp4: long edge <= 1280, 30 fps CFR, rotation applied, no audio."""
    src, out_dir = Path(src), Path(out_dir)
    if float(_probe(src)["format"]["duration"]) > max_s:
        raise ValueError("too_long")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "prepared.mp4"
    # ffmpeg autorotates by default (display matrix applied before filters).
    vf = ("scale='if(gt(iw,ih),min(1280,iw),-2)':'if(gt(iw,ih),-2,min(1280,ih))',"
          "scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=30")
    subprocess.run(
        [_bin("ffmpeg"), "-y", "-v", "error", "-i", str(src), "-an", "-vf", vf,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-fps_mode", "cfr",
         "-movflags", "+faststart", str(out)],
        check=True,
    )
    info = _probe(out)
    s = info["streams"][0]
    return PreparedVideo(out, _sha256(out), float(info["format"]["duration"]),
                         int(s["width"]), int(s["height"]))


def extract_frame(video: Path, t_s: float, out: Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [_bin("ffmpeg"), "-y", "-v", "error", "-ss", f"{t_s:.3f}", "-i", str(video),
         "-frames:v", "1", "-q:v", "2", str(out)],
        check=True,
    )
    return out


def sample_frames(video: Path, fps: float, out_dir: Path) -> list[tuple[float, Path]]:
    """Frames at `fps`; frame i (0-based) has timestamp i / fps."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [_bin("ffmpeg"), "-y", "-v", "error", "-i", str(video), "-vf", f"fps={fps}",
         "-q:v", "2", str(out_dir / "frame_%05d.jpg")],
        check=True,
    )
    files = sorted(out_dir.glob("frame_*.jpg"))
    return [(i / fps, p) for i, p in enumerate(files)]
