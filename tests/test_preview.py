"""D4: the unaligned SfM walk preview (PCA of camera centres)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from fixtures.sfm_synthetic import make_scene
from walktwin.preview import sfm_preview
from walktwin.sessions import to_jsonable


def _sfm(centers, status="completed", with_r=True):
    down = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]  # columns: right, down (-z), forward
    frames = []
    for i, c in enumerate(centers):
        f = {"t_s": 0.5 * i, "center": list(c)}
        if with_r:
            f["R"] = down
            f["K"] = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        frames.append(f)
    return {"status": status, "frames": frames, "points": [], "registered_fraction": 1.0,
            "elapsed_ms": 1, "error": None if status == "completed" else "no_floor_plane"}


def test_none_when_failed_or_too_few_frames():
    pts = [(0, 0, 0), (1, 0, 0), (2, 0.1, 0)]
    assert sfm_preview(None) is None
    assert sfm_preview(_sfm(pts, status="failed")) is None
    assert sfm_preview(_sfm(pts[:2])) is None
    assert sfm_preview(_sfm([(0, 0, 0)] * 3)) is None  # no spread at all


def test_centred_at_first_frame_walking_is_plus_v():
    # walk mostly along -x with a small sideways drift, in arbitrary SfM units
    pts = [(-0.3 * i, 0.02 * i * i, 1.0) for i in range(10)]
    out = sfm_preview(_sfm(pts))
    assert out["note"] == "unaligned, SfM units"
    p = out["points"]
    assert [q["t_s"] for q in p] == [0.5 * i for i in range(10)]
    assert p[0]["u"] == pytest.approx(0.0, abs=1e-12) and p[0]["v"] == pytest.approx(0.0, abs=1e-12)
    assert p[-1]["v"] > 0  # the walk proceeds along +v
    assert abs(p[-1]["v"]) > abs(p[-1]["u"])  # v is the main (first) component
    # distances are preserved (an orthonormal projection of a planar walk)
    d_sfm = math.dist(pts[0][:2], pts[-1][:2])
    assert math.hypot(p[-1]["u"], p[-1]["v"]) == pytest.approx(d_sfm, rel=1e-9)


def test_sorted_by_time_and_works_without_rotations():
    pts = [(0, 0, 0), (0, 1, 0), (0, 2, 0.1), (0.1, 3, 0)]
    sfm = _sfm(pts, with_r=False)
    sfm["frames"] = list(reversed(sfm["frames"]))
    out = sfm_preview(sfm)
    assert [q["t_s"] for q in out["points"]] == sorted(q["t_s"] for q in out["points"])
    assert out["points"][-1]["v"] > 0


def test_synthetic_walk_is_a_top_view_not_a_mirror():
    sfm, _graph = make_scene()
    out = sfm_preview(to_jsonable(sfm))
    p = np.array([[q["u"], q["v"]] for q in out["points"]])
    assert len(p) == len(sfm.frames)
    # true walk (graph metres) goes east, then turns left (north): seen from above
    # with +v along the walk, a left turn has the signed area of a counter-clockwise loop
    q = np.roll(p, -1, axis=0)  # close the loop: the signed area is then translation-free
    area = 0.5 * float(np.sum(p[:, 0] * q[:, 1] - q[:, 0] * p[:, 1]))
    assert area > 0
    # accepts the dataclass too
    assert sfm_preview(sfm) == out
