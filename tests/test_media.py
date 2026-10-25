import json
import subprocess
from pathlib import Path

import pytest

from walktwin import media

FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"


def _run(args):
    subprocess.run([FFMPEG, "-y", "-v", "error", *args], check=True)


def _probe(path: Path) -> dict:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


@pytest.fixture(scope="session")
def hevc_portrait(tmp_path_factory) -> Path:
    # Portrait is encoded directly as 1080x1920 (no rotation display matrix).
    p = tmp_path_factory.mktemp("clips") / "portrait_hevc.mov"
    _run(["-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30:duration=5",
          "-c:v", "libx265", "-pix_fmt", "yuv420p", "-tag:v", "hvc1", str(p)])
    return p


@pytest.fixture(scope="session")
def solid5(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("clips") / "solid5.mp4"
    _run(["-f", "lavfi", "-i", "color=c=teal:size=320x240:rate=30:duration=5",
          "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)])
    return p


@pytest.fixture(scope="session")
def long200(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("clips") / "long200.mp4"
    _run(["-f", "lavfi", "-i", "testsrc=size=64x64:rate=1:duration=200",
          "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)])
    return p


@pytest.fixture(scope="session")
def prepared(hevc_portrait, tmp_path_factory):
    return media.prepare_video(hevc_portrait, tmp_path_factory.mktemp("prep"))


def test_prepare_hevc_portrait_mov(prepared):
    info = _probe(prepared.path)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert v["codec_name"] == "h264"
    assert v["pix_fmt"] == "yuv420p"
    assert v["height"] > v["width"]
    assert max(v["width"], v["height"]) == 1280
    assert not any(s["codec_type"] == "audio" for s in info["streams"])
    assert abs(float(info["format"]["duration"]) - 5) < 0.2
    assert abs(prepared.duration_s - 5) < 0.2
    assert (prepared.width, prepared.height) == (v["width"], v["height"])
    assert len(prepared.sha256) == 64


def test_too_long_rejected(long200, tmp_path):
    with pytest.raises(ValueError, match="too_long"):
        media.prepare_video(long200, tmp_path)


def test_extract_frame(prepared, tmp_path):
    # textured clip: a solid-colour JPEG compresses below 1 KB
    out = media.extract_frame(prepared.path, 2.5, tmp_path / "f.jpg")
    assert out == tmp_path / "f.jpg"
    assert out.exists() and out.stat().st_size > 1024
    assert out.read_bytes()[:2] == b"\xff\xd8"


def test_sample_frames_timestamps(solid5, tmp_path):
    frames = media.sample_frames(solid5, 2, tmp_path / "frames")
    assert len(frames) == 10
    assert [t for t, _ in frames] == [i * 0.5 for i in range(10)]
    assert all(p.exists() and p.stat().st_size > 0 for _, p in frames)
