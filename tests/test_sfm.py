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
    scale_alignment,
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


def test_fit_alignment_mirrored_graph_reflects_but_disagrees():
    # A truly mirrored graph (loop walk, wide lateral spread) fails the proper fit
    # badly, so the reflected fit is accepted, but the badge never says "agrees".
    sfm, graph = make_scene(mirror=True)
    al = fit_alignment(sfm, graph)
    assert al._reflected
    assert al.residual_m < 0.05
    assert al.scale == pytest.approx(0.37, rel=0.01)
    by_t = {f.t_s: f for f in sfm.frames}
    kf = graph.keyframes[3]
    x, y = to_graph_xy(al, by_t[kf.t_s].center)
    assert math.hypot(x - kf.x, y - kf.y) < 0.05
    assert scale_badge(al) == "disagrees"


def test_straight_walk_with_noise_never_reflects():
    # Ruling R25: a near-collinear path cannot tell a mirror apart; never reflect.
    sfm0, graph0 = make_scene(waypoints=[(1.0, 4.0), (11.0, 4.0)])
    for seed in range(20):
        rng = np.random.default_rng(seed)
        kfs = [k.model_copy(update={"x": k.x + rng.normal(0, 0.15), "y": k.y + rng.normal(0, 0.15)})
               for k in graph0.keyframes]
        frames = [dataclasses.replace(
            f, center=tuple(np.array(f.center) + np.r_[rng.normal(0, 0.05 / 0.37, 2), 0.0]))
            for f in sfm0.frames]
        al = fit_alignment(dataclasses.replace(sfm0, frames=frames),
                           graph0.model_copy(update={"keyframes": kfs}))
        assert not al._reflected, f"seed {seed} reflected"


def test_floor_chosen_over_denser_ceiling():
    # The ceiling is also parallel to the path at a consistent distance (1.2 m);
    # the floor is the plane the cameras' image-down direction points at.
    sfm, graph = make_scene(n_floor=400, n_ceiling=3000)
    al = fit_alignment(sfm, graph)
    assert abs(al.eye_height_m - 1.5) < 0.02
    assert al.floor_offset == pytest.approx(-0.8, abs=0.02)


def test_floor_found_when_walls_dominate():
    # reviewer construction: 1600 wall + 300 ceiling points, only 100 on the floor
    sfm, graph = make_scene(n_floor=100, n_ceiling=300)
    al = fit_alignment(sfm, graph)
    assert abs(al.floor_offset - (-0.8)) * 0.37 < 0.05  # within 5 cm in metres
    assert abs(al.eye_height_m - 1.5) < 0.05


def test_no_floor_points_raises_no_floor_plane():
    sfm, graph = make_scene(n_floor=0, n_ceiling=300)
    with pytest.raises(ValueError, match="no_floor_plane"):
        fit_alignment(sfm, graph)


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("n_floor,noise_m", [(300, 0.03), (1500, 0.07)])
def test_noisy_low_texture_floor_still_found(n_floor, noise_m, seed):
    # I5: real phone floors are sparse and noisy. 12 x 8 m room, every point
    # (floor, walls, ceiling) with sigma noise in metres; the floor must be found.
    sfm, graph = make_scene(n_floor=n_floor, noise_m=noise_m, seed=seed)
    al = fit_alignment(sfm, graph)
    assert abs(al.floor_offset - (-0.8)) * 0.37 < 0.05  # within 5 cm in metres
    assert np.dot(al.floor_normal, (0, 0, 1)) > 0.995
    assert abs(al.eye_height_m - 1.5) < 0.05
    assert scale_badge(al) == "agrees"


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("noise_m", [0.01, 0.03, 0.07])
def test_no_floor_points_raises_no_floor_plane_at_any_noise(noise_m, seed):
    # wall dominance with no floor points: never accept a slice along the wall feet
    sfm, graph = make_scene(n_floor=0, n_ceiling=300, noise_m=noise_m, seed=seed)
    with pytest.raises(ValueError, match="no_floor_plane"):
        fit_alignment(sfm, graph)


def test_keyframe_between_frames_is_interpolated():
    # keyframes at t + 0.25 s fall halfway between 2 fps frames; interpolating the
    # bracketing centres keeps the fit exact (nearest-frame would be 0.3 m off)
    sfm, graph = make_scene()
    shifted = []
    for k in graph.keyframes[:-1]:
        shifted.append(k.model_copy(update={"t_s": k.t_s + 0.25, "x": k.x + 0.3 * _dir(k)[0],
                                            "y": k.y + 0.3 * _dir(k)[1]}))
    al = fit_alignment(sfm, graph.model_copy(update={"keyframes": shifted}))
    assert al.residual_m < 0.05


def _dir(kf):
    h = math.radians(kf.heading_deg)  # clockwise from +y
    return math.sin(h), math.cos(h)


def test_alignment_hash_stable():
    sfm, graph = make_scene()
    a1 = fit_alignment(sfm, graph)
    a2 = fit_alignment(sfm, graph)
    assert a1.hash == a2.hash
    assert len(a1.hash) == 64 and all(c in "0123456789abcdef" for c in a1.hash)
    sfm_b, graph_b = make_scene(shift=(2.5, -1.0))
    assert fit_alignment(sfm_b, graph_b).hash != a1.hash


def test_scale_alignment_scales_graph_xy_and_eye_height():
    # D3: the anchored (accepted-frame) alignment is the unanchored one times f
    sfm, graph = make_scene()
    al = fit_alignment(sfm, graph)
    f = 1.27
    sc = scale_alignment(al, f)
    assert sc.scale == pytest.approx(al.scale * f)
    assert (sc.tx, sc.ty) == pytest.approx((al.tx * f, al.ty * f))
    assert sc.eye_height_m == pytest.approx(al.eye_height_m * f)
    assert sc.residual_m == pytest.approx(al.residual_m * f)
    assert sc.yaw_rad == al.yaw_rad and sc.floor_normal == al.floor_normal
    assert sc.floor_offset == al.floor_offset and sc._reflected == al._reflected
    for fr in sfm.frames[::5]:
        x0, y0 = to_graph_xy(al, fr.center)
        x1, y1 = to_graph_xy(sc, fr.center)
        assert (x1, y1) == pytest.approx((f * x0, f * y0), abs=1e-9)
        assert height_above_floor_m(sc, fr.center) == pytest.approx(f * height_above_floor_m(al, fr.center))
    assert sc.hash != al.hash and len(sc.hash) == 64
    assert scale_alignment(al, f).hash == sc.hash  # deterministic
    assert scale_alignment(al, 1.0).hash == al.hash  # same recipe as fit_alignment


def test_scale_alignment_keeps_reflection_and_rejects_bad_factor():
    mirrored = fit_alignment(*make_scene(mirror=True))
    sc = scale_alignment(mirrored, 0.9)
    assert sc._reflected and scale_badge(sc) == "disagrees"
    assert sc.hash != scale_alignment(dataclasses.replace(mirrored, _reflected=False), 0.9).hash
    for bad in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            scale_alignment(mirrored, bad)


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
    two = graph.model_copy(update={"keyframes": graph.keyframes[:2]})
    with pytest.raises(ValueError, match="too_few_matches"):
        fit_alignment(sfm, two)


def test_run_sfm_fails_without_floor(monkeypatch, tmp_path):
    from walktwin import sfm as sfm_mod
    wall_only, _ = make_scene(n_floor=0, n_ceiling=300)
    monkeypatch.setattr(sfm_mod, "_reconstruct",
                        lambda video, work_dir, fps: (wall_only.frames, wall_only.points, len(wall_only.frames)))
    bogus = media.PreparedVideo(tmp_path / "x.mp4", "0" * 64, 5.0, 320, 240)
    res = run_sfm(bogus, tmp_path / "sfm")
    assert res.status == "failed" and res.error.startswith("no_floor_plane")
    # M11: the registered camera path is kept, so the walk can still be previewed
    assert res.frames == wall_only.frames
    assert res.registered_fraction == pytest.approx(1.0)
    with_floor, _ = make_scene()
    monkeypatch.setattr(sfm_mod, "_reconstruct",
                        lambda video, work_dir, fps: (with_floor.frames, with_floor.points, len(with_floor.frames)))
    assert run_sfm(bogus, tmp_path / "sfm").status == "completed"


def test_run_sfm_floor_failure_keeps_real_registered_fraction(monkeypatch, tmp_path):
    from walktwin import sfm as sfm_mod
    wall_only, _ = make_scene(n_floor=0, n_ceiling=300)
    n_sampled = 2 * len(wall_only.frames)  # half the sampled frames registered
    monkeypatch.setattr(sfm_mod, "_reconstruct",
                        lambda video, work_dir, fps: (wall_only.frames, wall_only.points, n_sampled))
    bogus = media.PreparedVideo(tmp_path / "x.mp4", "0" * 64, 5.0, 320, 240)
    res = run_sfm(bogus, tmp_path / "sfm")
    assert res.status == "failed" and res.error.startswith("no_floor_plane")
    assert len(res.frames) == len(wall_only.frames)
    assert res.registered_fraction == pytest.approx(0.5)
    assert res.elapsed_ms >= 0


def test_from_graph_xyz_defined_before_main_block():
    import inspect
    from walktwin import sfm as sfm_mod
    src = inspect.getsource(sfm_mod)
    assert src.index("def from_graph_xyz") < src.index('if __name__ == "__main__":')


def test_run_sfm_default_fps_is_4():
    import inspect
    assert inspect.signature(run_sfm).parameters["fps"].default == 4.0


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
