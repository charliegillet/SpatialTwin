import dataclasses
import math
import subprocess

import numpy as np
import pytest

from fixtures.sfm_synthetic import make_scene, rot_axis
from walktwin import media
from walktwin.sfm import (
    fit_alignment,
    height_above_floor_m,
    run_sfm,
    scale_badge,
    to_graph_xy,
)

FFMPEG = "/opt/homebrew/bin/ffmpeg"


def _yaw_err_deg(a: float, b: float) -> float:
    return abs(math.degrees(math.atan2(math.sin(a - b), math.cos(a - b))))


def test_fit_alignment_recovers_known_transform():
    sfm, graph = make_scene(scale=0.37, yaw_deg=30.0, shift=(2.0, -1.0))
    al = fit_alignment(sfm, graph)
    assert al.scale == pytest.approx(0.37, rel=0.01)
    assert _yaw_err_deg(al.yaw_rad, math.radians(30.0)) < 1.0
    assert al.tx == pytest.approx(2.0, abs=0.05)
    assert al.ty == pytest.approx(-1.0, abs=0.05)
    assert abs(al.eye_height_m - 1.5) < 0.02
    assert al.residual_m < 0.05
    # floor at z_sfm = 0.8 with the normal toward the cameras (+z)
    assert np.dot(al.floor_normal, (0, 0, 1)) > 0.999
    assert al.floor_offset == pytest.approx(-0.8, abs=0.02)
    assert scale_badge(al) == "agrees"


def test_fit_alignment_arbitrary_orientation_round_trips():
    # SfM "up" is unknown: tilt the whole SfM frame; the floor plane defines up.
    tilt = rot_axis((0.3, -1.0, 0.4), math.radians(110))
    sfm, graph = make_scene(tilt=tilt)
    al = fit_alignment(sfm, graph)
    assert al.scale == pytest.approx(0.37, rel=0.01)
    assert abs(al.eye_height_m - 1.5) < 0.02
    assert al.residual_m < 0.05
    by_t = {f.t_s: f for f in sfm.frames}
    for kf in graph.keyframes:
        x, y = to_graph_xy(al, by_t[kf.t_s].center)
        assert math.hypot(x - kf.x, y - kf.y) < 0.05
        assert height_above_floor_m(al, by_t[kf.t_s].center) == pytest.approx(1.5, abs=0.03)


def test_fit_alignment_handles_mirrored_graph():
    sfm, graph = make_scene(mirror=True)
    al = fit_alignment(sfm, graph)
    assert al.residual_m < 0.05
    assert al.scale == pytest.approx(0.37, rel=0.01)
    by_t = {f.t_s: f for f in sfm.frames}
    kf = graph.keyframes[3]
    x, y = to_graph_xy(al, by_t[kf.t_s].center)
    assert math.hypot(x - kf.x, y - kf.y) < 0.05


def test_floor_chosen_over_denser_ceiling():
    # The ceiling is also parallel to the path at a consistent distance (1.2 m);
    # the floor is the plane the cameras' image-down direction points at.
    sfm, graph = make_scene(n_floor=400, n_ceiling=3000)
    al = fit_alignment(sfm, graph)
    assert abs(al.eye_height_m - 1.5) < 0.02
    assert al.floor_offset == pytest.approx(-0.8, abs=0.02)


def test_alignment_hash_stable():
    sfm, graph = make_scene()
    a1 = fit_alignment(sfm, graph)
    a2 = fit_alignment(sfm, graph)
    assert a1.hash == a2.hash
    assert len(a1.hash) == 64 and all(c in "0123456789abcdef" for c in a1.hash)
    sfm_b, graph_b = make_scene(shift=(2.5, -1.0))
    assert fit_alignment(sfm_b, graph_b).hash != a1.hash


def test_scale_badge_disagrees_when_eye_height_off():
    # graph keyframes 1.3x too large (a bad anchor) -> SfM-implied eye height 1.95 m
    sfm, graph = make_scene(graph_scale=1.3)
    al = fit_alignment(sfm, graph)
    assert al.scale == pytest.approx(0.37 * 1.3, rel=0.01)
    assert al.eye_height_m == pytest.approx(1.95, abs=0.03)
    assert scale_badge(al) == "disagrees"
    good = fit_alignment(*make_scene())
    assert scale_badge(dataclasses.replace(good, residual_m=0.6)) == "disagrees"


def test_fit_alignment_too_few_matches():
    sfm, graph = make_scene()
    far = graph.model_copy(update={"keyframes": [
        k.model_copy(update={"t_s": k.t_s + 1000.0}) for k in graph.keyframes
    ]})
    with pytest.raises(ValueError, match="too_few_matches"):
        fit_alignment(sfm, far)


@pytest.fixture
def blank_clip(tmp_path):
    p = tmp_path / "blank.mp4"
    subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-f", "lavfi",
         "-i", "color=c=gray:size=320x240:rate=30:duration=5",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)],
        check=True,
    )
    return media.prepare_video(p, tmp_path / "prep")


def test_run_sfm_failed_on_blank_video(blank_clip, tmp_path):
    res = run_sfm(blank_clip, tmp_path / "sfm")
    assert res.status == "failed"
    assert res.error
    assert res.frames == [] and res.registered_fraction == 0.0
    assert res.elapsed_ms >= 0


def test_run_sfm_never_raises_on_missing_file(tmp_path):
    bogus = media.PreparedVideo(tmp_path / "nope.mp4", "0" * 64, 5.0, 320, 240)
    res = run_sfm(bogus, tmp_path / "sfm")
    assert res.status == "failed" and res.error
