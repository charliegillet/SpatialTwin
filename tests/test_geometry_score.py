"""Geometry score: the separate, measured critic.

All scenes are synthetic: SfmResult and Alignment are built directly with an
identity-like alignment (scale 1, yaw 0, floor z = 0), so graph metres equal
SfM units and nothing here depends on pycolmap.
"""
from __future__ import annotations

import math
import os
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

from fixtures.sfm_synthetic import ROOM_D, ROOM_W, K, _cam_to_world, make_scene, rot_axis
from walktwin import geometry_score as gs
from walktwin.contracts import Door, Keyframe, Measure, VenueGraph, Zone
from walktwin.geometry_score import (
    Crossing,
    GeometryScore,
    is_regression,
    score_geometry,
    select_heldout_t_s,
)
from walktwin.media import PreparedVideo
from walktwin.sfm import (
    Alignment,
    SfmFrame,
    SfmResult,
    fit_alignment,
    from_graph_xyz,
    height_above_floor_m,
    to_graph_xy,
)

EYE = 1.5
W, H = 1280, 720

ALIGN = Alignment(scale=1.0, yaw_rad=0.0, tx=0.0, ty=0.0, floor_normal=(0.0, 0.0, 1.0),
                  floor_offset=0.0, residual_m=0.0, eye_height_m=EYE, hash="a-test")


# ----------------------------------------------------------------------- builders


def _zone(zid: str, rect) -> Zone:
    return Zone(id=zid, name=zid, rect=tuple(float(v) for v in rect), occupants=0, evidence=[])


def _door(did: str, a: str, b: str, pos, width: float = 0.9) -> Door:
    return Door(id=did, a=a, b=b, kind="door", state="open",
                clear_width=Measure(low_m=width, high_m=width, basis="estimated"),
                position=(float(pos[0]), float(pos[1])), evidence=[])


def _graph(zones, doors=(), keyframes=()) -> VenueGraph:
    return VenueGraph(schema_version="1", video_sha256="t", anchor=None,
                      zones=list(zones), doors=list(doors), keyframes=list(keyframes))


def _frame(t: float, x: float, y: float, heading_deg: float = 0.0) -> SfmFrame:
    R = _cam_to_world(math.radians(heading_deg))
    return SfmFrame(t_s=t, center=(float(x), float(y), EYE), R=R.tolist(), K=K)


def _sfm(path, points=()) -> SfmResult:
    frames = [_frame(t, x, y) for t, x, y in path]
    return SfmResult("completed", frames, [tuple(map(float, p)) for p in points], 1.0, 0, None)


TWO_ROOMS = [_zone("Z1", (0, 0, 4, 4)), _zone("Z2", (4, 0, 4, 4))]


# --------------------------------------------------------------------- crossings


def test_path_through_wall_is_crossing():
    sfm = _sfm([(0.0, 2.0, 2.0), (1.0, 6.0, 2.0)])
    score = score_geometry(_graph(TWO_ROOMS), sfm, ALIGN)
    assert len(score.illegal_crossings) == 1  # shared edge counted once
    c = score.illegal_crossings[0]
    assert c.edge == "Z1.east"
    assert c.t_s == pytest.approx(0.5)
    assert (c.x, c.y) == pytest.approx((4.0, 2.0))


def test_door_removes_crossing():
    sfm = _sfm([(0.0, 2.0, 2.0), (1.0, 6.0, 2.0)])
    graph = _graph(TWO_ROOMS, [_door("D1", "Z1", "Z2", (4.0, 2.0))])
    assert score_geometry(graph, sfm, ALIGN).illegal_crossings == []


def test_crossing_near_door_tolerated():
    # door gap on x = 4 spans y in [0.55, 1.45]
    graph = _graph(TWO_ROOMS, [_door("D1", "Z1", "Z2", (4.0, 1.0), width=0.9)])
    near = _sfm([(0.0, 2.0, 1.45 + 0.4), (1.0, 6.0, 1.45 + 0.4)])
    assert score_geometry(graph, near, ALIGN).illegal_crossings == []
    # control: beyond the 0.5 m tolerance it is a crossing again
    far = _sfm([(0.0, 2.0, 1.45 + 0.6), (1.0, 6.0, 1.45 + 0.6)])
    assert len(score_geometry(graph, far, ALIGN).illegal_crossings) == 1


def test_door_on_one_edge_does_not_open_another():
    # a door on Z1's north edge leaves the shared east wall solid
    graph = _graph(TWO_ROOMS, [_door("D1", "Z1", "OUTSIDE", (2.0, 4.0))])
    sfm = _sfm([(0.0, 2.0, 2.0), (1.0, 6.0, 2.0)])
    assert [c.edge for c in score_geometry(graph, sfm, ALIGN).illegal_crossings] == ["Z1.east"]


def test_crossings_named_by_side_and_time_sorted():
    graph = _graph([_zone("Z1", (0, 0, 4, 4)), _zone("Z2", (0, 4, 4, 4)), _zone("Z3", (4, 0, 4, 4))])
    # Z1 -> Z2 (north side of Z1), back, then Z1 -> Z3 (east side)
    sfm = _sfm([(0.0, 2.0, 2.0), (1.0, 2.0, 6.0), (2.0, 2.0, 2.0), (3.0, 6.0, 2.0)])
    cs = score_geometry(graph, sfm, ALIGN).illegal_crossings
    assert [(c.edge, c.t_s) for c in cs] == [("Z1.north", 0.5), ("Z1.north", 1.5), ("Z1.east", 2.5)]


def test_leaving_every_zone_is_one_outside_crossing():
    graph = _graph([_zone("Z1", (0, 0, 4, 4))])
    path = [(0.0, 2.0, 2.0), (1.0, 3.5, 2.0), (2.0, 5.0, 2.0), (3.0, 6.0, 2.0),
            (4.0, 5.0, 2.0), (5.0, 3.0, 2.0)]
    cs = score_geometry(graph, _sfm(path), ALIGN).illegal_crossings
    assert len(cs) == 1
    assert cs[0].edge == "outside"
    assert cs[0].t_s == pytest.approx(1.5)
    assert (cs[0].x, cs[0].y) == pytest.approx((5.0, 2.0))
    # within 0.15 m of a rect is not "outside"; beyond it is
    assert score_geometry(graph, _sfm([(0.0, 4.1, 2.0)]), ALIGN).illegal_crossings == []
    cs = score_geometry(graph, _sfm([(0.0, 4.2, 2.0)]), ALIGN).illegal_crossings
    assert [(c.edge, c.t_s) for c in cs] == [("outside", 0.0)]


def test_two_outside_runs_are_two_crossings():
    graph = _graph([_zone("Z1", (0, 0, 4, 4))])
    path = [(0.0, 2.0, 2.0), (1.0, 5.0, 2.0), (2.0, 3.0, 2.0), (3.0, 5.0, 2.0), (4.0, 2.0, 2.0)]
    cs = score_geometry(graph, _sfm(path), ALIGN).illegal_crossings
    assert [(c.edge, c.t_s) for c in cs] == [("outside", 0.5), ("outside", 2.5)]


# ------------------------------------------------------------------ wall support


def _wall_points(rng: np.random.Generator, n_per_wall: int = 200) -> np.ndarray:
    """Points on the modelled walls of TWO_ROOMS (outer box 8 x 4 plus x = 4), 0.5-2.0 m high."""
    walls = []
    for _ in range(n_per_wall):
        walls.append((rng.uniform(0, 8), 0.0))
        walls.append((rng.uniform(0, 8), 4.0))
        walls.append((0.0, rng.uniform(0, 4)))
        walls.append((8.0, rng.uniform(0, 4)))
        walls.append((4.0, rng.uniform(0, 4)))
    xy = np.asarray(walls) + rng.normal(0, 0.03, (len(walls), 2))
    z = rng.uniform(0.5, 2.0, len(walls))
    return np.c_[xy, z]


def test_wall_support():
    rng = np.random.default_rng(1)
    pts = _wall_points(rng)
    # floor and ceiling points sit outside the 0.5-2.0 m band and must be ignored
    floor = np.c_[rng.uniform(0, 8, 300), rng.uniform(0, 4, 300), np.zeros(300)]
    ceiling = np.c_[rng.uniform(0, 8, 300), rng.uniform(0, 4, 300), np.full(300, 2.7)]
    sfm = _sfm([(0.0, 2.0, 2.0)], points=np.vstack([pts, floor, ceiling]))
    good = score_geometry(_graph(TWO_ROOMS), sfm, ALIGN)
    assert good.wall_support >= 0.95
    assert good.unexplained_points < 0.05

    shifted = _graph([_zone("Z1", (1, 1, 4, 4)), _zone("Z2", (5, 1, 4, 4))])
    assert score_geometry(shifted, sfm, ALIGN).wall_support <= 0.2


def test_unexplained_points():
    rng = np.random.default_rng(2)
    inside = _wall_points(rng, 40)                                   # 200 points
    outside = np.c_[rng.uniform(9.5, 11, 200), rng.uniform(0, 4, 200), np.full(200, 1.0)]
    sfm = _sfm([(0.0, 2.0, 2.0)], points=np.vstack([inside, outside]))
    s = score_geometry(_graph(TWO_ROOMS), sfm, ALIGN)
    assert s.unexplained_points == pytest.approx(0.5, abs=0.02)
    assert s.wall_support == pytest.approx(0.5, abs=0.05)


def test_door_gap_is_not_wall():
    # points standing in a 2 m door gap are not wall support
    graph = _graph([_zone("Z1", (0, 0, 4, 4))], [_door("D1", "Z1", "OUTSIDE", (2.0, 4.0), width=2.0)])
    pts = [(x, 4.0, 1.0) for x in np.linspace(1.3, 2.7, 15)]
    s = score_geometry(graph, _sfm([(0.0, 2.0, 2.0)], points=pts), ALIGN)
    assert s.wall_support == 0.0


def test_scores_through_a_fitted_tilted_alignment():
    # arbitrary SfM orientation and scale: the measurement goes through the real alignment
    sfm, kf_graph = make_scene(tilt=rot_axis((0.3, -1.0, 0.4), math.radians(110)))
    al = fit_alignment(sfm, kf_graph)
    room = _graph([_zone("Z1", (0, 0, ROOM_W, ROOM_D))], keyframes=kf_graph.keyframes)
    s = score_geometry(room, sfm, al)
    assert s.alignment_hash == al.hash
    assert s.illegal_crossings == []
    assert s.wall_support >= 0.95 and s.unexplained_points < 0.02
    # split the room with a solid wall across the walked path: crossings appear
    split = _graph([_zone("Z1", (0, 0, 6, ROOM_D)), _zone("Z2", (6, 0, ROOM_W - 6, ROOM_D))],
                   keyframes=kf_graph.keyframes)
    cs = score_geometry(split, sfm, al).illegal_crossings
    assert len(cs) >= 2 and {c.edge for c in cs} == {"Z1.east"}
    assert all(c.x == pytest.approx(6.0, abs=0.05) for c in cs)


# ---------------------------------------------------------------- is_regression


def _score(n_cross=0, support=0.8, within=None, h="a-test") -> GeometryScore:
    cs = [Crossing(t_s=float(i), x=0.0, y=0.0, edge="Z1.east") for i in range(n_cross)]
    return GeometryScore(alignment_hash=h, illegal_crossings=cs, wall_support=support,
                         unexplained_points=0.1, edge_chamfer_px=None if within is None else 3.0,
                         edge_within_5px=within, heldout_t_s=[])


def test_is_regression():
    base = _score(n_cross=2, support=0.80, within=0.60)
    assert not is_regression(base, _score(n_cross=2, support=0.80, within=0.60))
    assert not is_regression(base, _score(n_cross=1, support=0.85, within=0.70))
    assert is_regression(base, _score(n_cross=3, support=0.80, within=0.60))
    assert not is_regression(base, _score(n_cross=2, support=0.79, within=0.60))   # within 0.02
    assert is_regression(base, _score(n_cross=2, support=0.77, within=0.60))
    assert not is_regression(base, _score(n_cross=2, support=0.80, within=0.56))   # within 0.05
    assert is_regression(base, _score(n_cross=2, support=0.80, within=0.54))
    # edge alignment is compared only when both sides have it
    assert not is_regression(base, _score(n_cross=2, support=0.80, within=None))
    assert not is_regression(_score(within=None), _score(within=0.0))


def test_is_regression_rejects_mismatched_alignment():
    with pytest.raises(ValueError):
        is_regression(_score(h="a-1"), _score(h="a-2"))


# ------------------------------------------------------------ inverse alignment


def test_from_graph_xyz_round_trips_to_graph_xy():
    rng = np.random.default_rng(7)
    worst = 0.0
    for i in range(100):
        n = rng.normal(size=3) * rng.uniform(0.5, 2.0)  # non-unit normals too
        al = Alignment(scale=float(rng.uniform(0.1, 5)), yaw_rad=float(rng.uniform(-math.pi, math.pi)),
                       tx=float(rng.uniform(-10, 10)), ty=float(rng.uniform(-10, 10)),
                       floor_normal=tuple(float(v) for v in n), floor_offset=float(rng.uniform(-3, 3)),
                       residual_m=0.0, eye_height_m=1.5, hash="h", _reflected=bool(i % 2))
        x, y, h = (float(v) for v in rng.uniform(-20, 20, 3))
        p = from_graph_xyz(al, x, y, h)
        gx, gy = to_graph_xy(al, p)
        gh = height_above_floor_m(al, p)
        worst = max(worst, abs(gx - x), abs(gy - y), abs(gh - h))
        # and the other direction: SfM point -> graph -> SfM point
        q = rng.uniform(-20, 20, 3)
        q2 = from_graph_xyz(al, *to_graph_xy(al, q), height_above_floor_m(al, q))
        worst = max(worst, float(np.abs(np.asarray(q2) - q).max()))
    assert worst < 1e-9


# --------------------------------------------------------------- edge alignment

ROOM = (0.0, 0.0, 8.0, 10.0)
DOOR_GAP = (3.4, 4.6)  # exit door on the north wall at (4, 10), 1.2 m wide
CAM = (4.0, 1.0)


def _render_room(rect=ROOM, gap=DOOR_GAP, cam=CAM, heading_deg=90.0) -> np.ndarray:
    """Ray-cast a grey-level image of one box room: floor, four walls, ceiling and a
    dark door opening (0-2 m) in the north wall. Step edges, so Canny lands on them.
    Pixel centres are at (j + 0.5, i + 0.5), the COLMAP convention."""
    x0, y0, w, h = rect
    x1, y1 = x0 + w, y0 + h
    ceil_h = 2.7
    Kinv = np.linalg.inv(np.asarray(K))
    R = _cam_to_world(math.radians(heading_deg))
    jj, ii = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
    d = (R @ Kinv @ np.stack([jj.ravel(), ii.ravel(), np.ones(W * H)])).T
    c = np.array([cam[0], cam[1], EYE])
    big = np.full(len(d), np.inf)
    with np.errstate(divide="ignore", invalid="ignore"):
        s_floor = np.where(d[:, 2] < 0, -c[2] / d[:, 2], big)
        s_ceil = np.where(d[:, 2] > 0, (ceil_h - c[2]) / d[:, 2], big)
        cand = {
            "north": np.where(d[:, 1] > 0, (y1 - c[1]) / d[:, 1], big),
            "south": np.where(d[:, 1] < 0, (y0 - c[1]) / d[:, 1], big),
            "east": np.where(d[:, 0] > 0, (x1 - c[0]) / d[:, 0], big),
            "west": np.where(d[:, 0] < 0, (x0 - c[0]) / d[:, 0], big),
        }
    names = list(cand)
    S = np.stack([cand[k] for k in names], axis=1)
    wall_i = np.argmin(S, axis=1)
    s_wall = S[np.arange(len(d)), wall_i]
    shade = {"north": 140, "south": 90, "east": 110, "west": 175}
    img = np.array([shade[names[k]] for k in wall_i], np.uint8)
    hit = c + s_wall[:, None] * d
    if gap is not None:
        door = (wall_i == names.index("north")) & (hit[:, 0] > gap[0]) & (hit[:, 0] < gap[1]) & (hit[:, 2] < 2.0)
        img[door] = 25
    img[s_floor < s_wall] = 60
    img[s_ceil < s_wall] = 215
    return img.reshape(H, W)


def _room_graph(dx=0.0, dy=0.0, with_door=True, extra_zones=()) -> VenueGraph:
    x0, y0, w, h = ROOM
    doors = [_door("D1", "Z1", "OUTSIDE", (4.0 + dx, 10.0 + dy), width=1.2)] if with_door else []
    return _graph([_zone("Z1", (x0 + dx, y0 + dy, w, h)), *extra_zones], doors,
                  [Keyframe(t_s=0.0, zone_id="Z1", x=CAM[0], y=CAM[1], heading_deg=90.0)])


def _room_sfm() -> SfmResult:
    frames = [_frame(0.0, *CAM, heading_deg=90.0), _frame(5.0, *CAM, heading_deg=90.0)]
    return SfmResult("completed", frames, [], 1.0, 0, None)


VIDEO = PreparedVideo(path=Path("unused.mp4"), sha256="x",
                      duration_s=6.0, width=W, height=H)


@pytest.fixture
def fake_frames(monkeypatch):
    """Serve the rendered image instead of decoding a video."""
    state = {"img": _render_room(), "calls": []}

    def fake_extract(video, t_s, out):
        state["calls"].append(t_s)
        cv2.imwrite(str(out), state["img"])
        return out

    monkeypatch.setattr(gs, "extract_frame", fake_extract)
    return state


def test_edge_chamfer_zero_on_synthetic_frame(fake_frames):
    s = score_geometry(_room_graph(), _room_sfm(), ALIGN, video=VIDEO, heldout_t_s=[5.0])
    assert fake_frames["calls"] == [5.0]
    assert s.heldout_t_s == [5.0]
    assert s.edge_chamfer_px is not None and s.edge_chamfer_px < 1.0
    assert s.edge_within_5px >= 0.98

    moved = score_geometry(_room_graph(dx=0.4, dy=-0.6), _room_sfm(), ALIGN, video=VIDEO,
                           heldout_t_s=[5.0])
    assert moved.edge_chamfer_px > 3.0
    assert moved.edge_within_5px < s.edge_within_5px - 0.2


def test_edge_alignment_none_without_video_or_heldout(fake_frames):
    s = score_geometry(_room_graph(), _room_sfm(), ALIGN)
    assert s.edge_chamfer_px is None and s.edge_within_5px is None
    s = score_geometry(_room_graph(), _room_sfm(), ALIGN, video=VIDEO, heldout_t_s=[])
    assert s.edge_chamfer_px is None and s.edge_within_5px is None
    assert fake_frames["calls"] == []


def test_occluded_walls_not_sampled(fake_frames):
    # A second room behind Z1's solid north wall: its far walls are hidden, so
    # projecting them would add phantom misses. They must not be sampled.
    fake_frames["img"] = _render_room(gap=None)
    behind = _zone("Z2", (0.0, 10.0, 8.0, 6.0))
    alone = score_geometry(_room_graph(with_door=False), _room_sfm(), ALIGN, video=VIDEO,
                           heldout_t_s=[5.0])
    with_z2 = score_geometry(_room_graph(with_door=False, extra_zones=[behind]), _room_sfm(),
                             ALIGN, video=VIDEO, heldout_t_s=[5.0])
    assert alone.edge_chamfer_px < 1.0
    assert with_z2.edge_chamfer_px == pytest.approx(alone.edge_chamfer_px, abs=0.02)
    # only the first sample of Z2's side walls, at the shared corners, stays visible
    frame = _room_sfm().frames[1]
    n_alone = len(gs._model_samples(frame, ALIGN, gs._walls(_room_graph(with_door=False)), [], W, H))
    g2 = _room_graph(with_door=False, extra_zones=[behind])
    n_z2 = len(gs._model_samples(frame, ALIGN, gs._walls(g2), [], W, H))
    assert n_alone > 100
    assert n_z2 - n_alone <= 2


@pytest.mark.skipif(shutil.which("ffmpeg") is None and not os.path.exists("/opt/homebrew/bin/ffmpeg"),
                    reason="ffmpeg not installed")
def test_edge_chamfer_through_real_video(tmp_path):
    from walktwin.media import _bin

    png = tmp_path / "room.png"
    cv2.imwrite(str(png), _render_room())
    mp4 = tmp_path / "room.mp4"
    subprocess.run([_bin("ffmpeg"), "-y", "-v", "error", "-loop", "1", "-i", str(png), "-t", "6",
                    "-r", "30", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", str(mp4)],
                   check=True)
    video = PreparedVideo(path=mp4, sha256="x", duration_s=6.0, width=W, height=H)
    s = score_geometry(_room_graph(), _room_sfm(), ALIGN, video=video, heldout_t_s=[5.0])
    assert s.edge_chamfer_px < 1.5
    assert s.edge_within_5px >= 0.95


def test_select_heldout_t_s():
    graph = _graph([_zone("Z1", (0, 0, 4, 4))], keyframes=[
        Keyframe(t_s=2.0, zone_id="Z1", x=1, y=1, heading_deg=0.0),
        Keyframe(t_s=6.0, zone_id="Z1", x=1, y=1, heading_deg=0.0)])
    sfm = _sfm([(t, 1.0, 1.0) for t in np.arange(0, 9.5, 0.5)])
    assert select_heldout_t_s(sfm, graph) == [0.0, 0.5, 3.5, 4.0, 4.5, 7.5, 8.0, 8.5, 9.0]
