"""Geometry score: the separate, measured critic of a venue graph.

Nothing here asks a model anything. Three measurements against the SfM
reconstruction, through the alignment frozen on iteration 0:

- Illegal crossings. The walker cannot walk through a wall, so every segment
  of the SfM camera path (projected to graph xy) that crosses a modelled wall
  away from a door is a timestamped error in the graph. Leaving every zone is
  also an error, reported once per run of outside frames with edge "outside".
- Wall support / unexplained points. Of the SfM points in the wall-height band,
  the share near a modelled wall, and the share outside every zone.
- Edge alignment, held-out frames only. The twin's floor-wall lines and door
  jambs are projected through the SfM poses into frames never sent to the
  critique, and compared with Canny edges by a distance transform (chamfer).
  Appearance metrics (SSIM, LPIPS) are deliberately not used.

Walls are zone-rect edges minus door gaps (door position +/- mid width / 2) for
each door within DOOR_ON_EDGE_M of the edge. Collinear overlapping edges of
neighbouring zones count once (the first zone in graph order names them).
Edge names are "<zone id>.<north|south|east|west>"; north is the +y side.

Every threshold below is a declared parameter (a model assumption to tune on
the day's captures), not a measurement.
"""
from __future__ import annotations

import math
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from walktwin.contracts import VenueGraph
from walktwin.media import PreparedVideo, extract_frame
from walktwin.sfm import Alignment, SfmFrame, SfmResult, from_graph_xyz, height_above_floor_m, to_graph_xy

# Declared parameters (model assumptions, not measurements).
DOOR_ON_EDGE_M = 0.5          # a door within this distance of a rect edge cuts a gap in it
DOOR_TOLERANCE_M = 0.5        # crossings within this distance of a door gap are tolerated
WALL_NEAR_M = 0.15            # "near a wall" for wall support
OUTSIDE_M = 0.15              # "outside every zone" beyond this distance from all rects
WALL_BAND_LOW_M = 0.5         # SfM points counted for wall support: this band above the floor
WALL_BAND_HIGH_M = 2.0
EDGE_WITHIN_PX = 5.0          # "aligned" edge sample
SAMPLE_STEP_PX = 5.0          # spacing of projected model samples
JAMB_HEIGHT_M = 2.0           # door jambs run 0 - 2.0 m at the gap ends
CANNY_LOW, CANNY_HIGH = 50, 150
HELDOUT_MIN_GAP_S = 1.0       # held-out frames are this far from every keyframe
NEAR_PLANE_M = 0.1            # model geometry closer to the camera than this is skipped
OCCLUSION_MARGIN_M = 0.05     # a wall must be this much nearer than a sample to hide it
HELDOUT_MATCH_S = 0.05        # a held-out t_s must match an SfM frame this closely
REGRESSION_WALL_SUPPORT = 0.02
REGRESSION_EDGE_WITHIN = 0.05

_COLLINEAR_EPS = 1e-6
_SIDES = ("north", "south", "east", "west")


@dataclass(frozen=True)
class Crossing:
    t_s: float
    x: float
    y: float
    edge: str  # "<zone id>.<north|south|east|west>" or "outside"


@dataclass(frozen=True)
class GeometryScore:
    alignment_hash: str
    illegal_crossings: list[Crossing]
    wall_support: float
    unexplained_points: float
    edge_chamfer_px: float | None
    edge_within_5px: float | None
    heldout_t_s: list[float] = field(default_factory=list)


# ------------------------------------------------------------------------ walls


@dataclass(frozen=True)
class _Edge:
    name: str
    horizontal: bool  # True: y = c, runs along x
    c: float
    lo: float
    hi: float


def _rect_edges(graph: VenueGraph) -> list[_Edge]:
    out = []
    for z in graph.zones:
        x, y, w, h = z.rect
        out += [
            _Edge(f"{z.id}.north", True, y + h, x, x + w),
            _Edge(f"{z.id}.south", True, y, x, x + w),
            _Edge(f"{z.id}.east", False, x + w, y, y + h),
            _Edge(f"{z.id}.west", False, x, y, y + h),
        ]
    return out


def _subtract(intervals: list[tuple[float, float]], cut: tuple[float, float]) -> list[tuple[float, float]]:
    a, b = cut
    out = []
    for lo, hi in intervals:
        if b <= lo or a >= hi:
            out.append((lo, hi))
            continue
        if a > lo:
            out.append((lo, a))
        if b < hi:
            out.append((b, hi))
    return out


def _door_gaps(graph: VenueGraph, e: _Edge, pad: float) -> list[tuple[float, float]]:
    """Along-edge gaps (position +/- mid width / 2 + pad) for doors on this edge."""
    gaps = []
    for d in graph.doors:
        px, py = d.position
        along, across = (px, py) if e.horizontal else (py, px)
        off = max(e.lo - along, 0.0, along - e.hi)
        if math.hypot(off, across - e.c) > DOOR_ON_EDGE_M:
            continue
        half = (d.clear_width.low_m + d.clear_width.high_m) / 4 + pad
        gaps.append((along - half, along + half))
    return gaps


def _walls(graph: VenueGraph, pad: float = 0.0) -> list[_Edge]:
    """Wall pieces: rect edges minus door gaps (widened by `pad`), shared edges once."""
    covered: dict[tuple[bool, float], list[tuple[float, float]]] = {}
    pieces = []
    for e in _rect_edges(graph):
        key = (e.horizontal, round(e.c / _COLLINEAR_EPS))
        free = [(e.lo, e.hi)]
        for span in covered.get(key, []):
            free = _subtract(free, span)
        covered.setdefault(key, []).append((e.lo, e.hi))
        for gap in _door_gaps(graph, e, pad):
            free = _subtract(free, gap)
        pieces += [_Edge(e.name, e.horizontal, e.c, lo, hi) for lo, hi in free if hi - lo > 1e-9]
    return pieces


def _jambs(graph: VenueGraph) -> list[tuple[float, float]]:
    """Graph xy of door gap ends, clipped to their edge, deduplicated."""
    seen, out = set(), []
    for e in _rect_edges(graph):
        for a, b in _door_gaps(graph, e, 0.0):
            for along in (a, b):
                along = min(max(along, e.lo), e.hi)
                xy = (along, e.c) if e.horizontal else (e.c, along)
                k = (round(xy[0], 3), round(xy[1], 3))
                if k not in seen:
                    seen.add(k)
                    out.append(xy)
    return out


def _wall_arrays(walls: list[_Edge]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    hz = np.array([w.horizontal for w in walls], bool)
    c = np.array([w.c for w in walls], float)
    lo = np.array([w.lo for w in walls], float)
    hi = np.array([w.hi for w in walls], float)
    return hz, c, lo, hi


def _dist_to_walls(xy: np.ndarray, walls: list[_Edge]) -> np.ndarray:
    """Distance from each point to the nearest wall piece (inf with no walls)."""
    if not walls or len(xy) == 0:
        return np.full(len(xy), np.inf)
    hz, c, lo, hi = _wall_arrays(walls)
    along = np.where(hz[None, :], xy[:, :1], xy[:, 1:2])
    across = np.where(hz[None, :], xy[:, 1:2], xy[:, :1])
    off = np.maximum(np.maximum(lo[None, :] - along, along - hi[None, :]), 0.0)
    return np.hypot(off, across - c[None, :]).min(axis=1)


def _dist_outside_rects(xy: np.ndarray, graph: VenueGraph) -> np.ndarray:
    """Distance from each point to the nearest zone rect (0 inside; inf with no zones)."""
    if not graph.zones or len(xy) == 0:
        return np.full(len(xy), np.inf)
    r = np.array([z.rect for z in graph.zones], float)
    x0, y0, x1, y1 = r[:, 0], r[:, 1], r[:, 0] + r[:, 2], r[:, 1] + r[:, 3]
    dx = np.maximum(np.maximum(x0[None, :] - xy[:, :1], xy[:, :1] - x1[None, :]), 0.0)
    dy = np.maximum(np.maximum(y0[None, :] - xy[:, 1:2], xy[:, 1:2] - y1[None, :]), 0.0)
    return np.hypot(dx, dy).min(axis=1)


# -------------------------------------------------------------------- crossings


def _segment_crossings(p0: np.ndarray, p1: np.ndarray, walls: list[_Edge]) -> list[tuple[float, float, float, str]]:
    """(segment param, x, y, edge name) for each wall piece the segment p0 -> p1 crosses.

    Half-open sign test so a frame lying exactly on a wall is crossed once, and
    a segment running along a wall does not cross it."""
    out = []
    for w in walls:
        a0, a1 = (p0[1], p1[1]) if w.horizontal else (p0[0], p1[0])
        d0, d1 = a0 - w.c, a1 - w.c
        if (d0 < 0) == (d1 < 0) or d0 == d1:
            continue
        s = d0 / (d0 - d1)
        q = p0 + s * (p1 - p0)
        along = q[0] if w.horizontal else q[1]
        if w.lo <= along <= w.hi:
            out.append((float(s), float(q[0]), float(q[1]), w.name))
    return out


def _crossings(graph: VenueGraph, frames: list[SfmFrame], xy: np.ndarray) -> list[Crossing]:
    if len(frames) == 0:
        return []
    t = np.array([f.t_s for f in frames], float)
    outside = _dist_outside_rects(xy, graph) > OUTSIDE_M
    walls = _walls(graph, pad=DOOR_TOLERANCE_M)
    out: list[Crossing] = []
    # one "outside" crossing per maximal run of outside frames
    i = 0
    while i < len(frames):
        if not outside[i]:
            i += 1
            continue
        t_s = (t[i - 1] + t[i]) / 2 if i > 0 else t[i]
        out.append(Crossing(t_s=float(t_s), x=float(xy[i, 0]), y=float(xy[i, 1]), edge="outside"))
        while i < len(frames) and outside[i]:
            i += 1
    # wall crossings on segments with both ends inside (or near) some zone
    for k in range(len(frames) - 1):
        if outside[k] or outside[k + 1]:
            continue
        t_mid = float((t[k] + t[k + 1]) / 2)
        for _, x, y, name in _segment_crossings(xy[k], xy[k + 1], walls):
            out.append(Crossing(t_s=t_mid, x=x, y=y, edge=name))
    out.sort(key=lambda c: c.t_s)
    return out


# ------------------------------------------------------------------ point cloud


def _point_scores(graph: VenueGraph, sfm: SfmResult, alignment: Alignment) -> tuple[float, float]:
    if not sfm.points:
        return 0.0, 0.0
    pts = np.asarray(sfm.points, float).reshape(-1, 3)
    h = _heights_many(alignment, pts)
    band = pts[(h >= WALL_BAND_LOW_M) & (h <= WALL_BAND_HIGH_M)]
    if len(band) == 0:
        return 0.0, 0.0
    xy = _graph_xy_many(alignment, band)
    near = _dist_to_walls(xy, _walls(graph)) <= WALL_NEAR_M
    unexplained = _dist_outside_rects(xy, graph) > OUTSIDE_M
    return float(near.mean()), float(unexplained.mean())


def _heights_many(alignment: Alignment, pts: np.ndarray) -> np.ndarray:
    """height_above_floor_m for many points, via the affine map it implements."""
    h0 = height_above_floor_m(alignment, (0.0, 0.0, 0.0))
    g = np.array([height_above_floor_m(alignment, e) - h0 for e in np.eye(3)])
    return h0 + pts @ g


def _graph_xy_many(alignment: Alignment, pts: np.ndarray) -> np.ndarray:
    """to_graph_xy for many points, via the affine map it implements."""
    o = np.array(to_graph_xy(alignment, (0.0, 0.0, 0.0)))
    ex = np.array(to_graph_xy(alignment, (1.0, 0.0, 0.0))) - o
    ey = np.array(to_graph_xy(alignment, (0.0, 1.0, 0.0))) - o
    ez = np.array(to_graph_xy(alignment, (0.0, 0.0, 1.0))) - o
    return o + pts @ np.stack([ex, ey, ez])


# --------------------------------------------------------------- edge alignment


def _clip_to_image(a: np.ndarray, b: np.ndarray, w: int, h: int) -> tuple[float, float] | None:
    """Liang-Barsky: parameter range of a -> b inside [0, w] x [0, h]."""
    t0, t1 = 0.0, 1.0
    d = b - a
    for p, q in ((-d[0], a[0]), (d[0], w - a[0]), (-d[1], a[1]), (d[1], h - a[1])):
        if p == 0:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return None
    return t0, t1


def _occluded(cam_xy: np.ndarray, q: np.ndarray, walls: list[_Edge]) -> np.ndarray:
    """True where a wall piece stands between the camera and graph point q (full-height walls)."""
    if not walls or len(q) == 0:
        return np.zeros(len(q), bool)
    hz, c, lo, hi = _wall_arrays(walls)
    d = q - cam_xy
    dist = np.hypot(d[:, 0], d[:, 1])
    ca = np.where(hz, cam_xy[1], cam_xy[0])                     # (M,)
    da = np.where(hz[None, :], d[:, 1:2], d[:, :1])             # (N, M)
    cb = np.where(hz, cam_xy[0], cam_xy[1])
    db = np.where(hz[None, :], d[:, :1], d[:, 1:2])
    with np.errstate(divide="ignore", invalid="ignore"):
        s = (c[None, :] - ca[None, :]) / da
    along = cb[None, :] + s * db
    limit = 1.0 - OCCLUSION_MARGIN_M / np.maximum(dist, 1e-12)
    hit = (da != 0) & (s > 0) & (s < limit[:, None]) & (along >= lo[None, :]) & (along <= hi[None, :])
    return hit.any(axis=1)


def _model_samples(frame: SfmFrame, alignment: Alignment, walls: list[_Edge],
                   jambs: list[tuple[float, float]], width: int, height: int) -> np.ndarray:
    """Pixel samples (N, 2), every SAMPLE_STEP_PX, of the visible floor-wall lines and
    door jambs. Pixel centres follow COLMAP: pixel (i, j) covers [j, j+1) x [i, i+1)."""
    segs = [((w.lo, w.c, 0.0), (w.hi, w.c, 0.0)) if w.horizontal else ((w.c, w.lo, 0.0), (w.c, w.hi, 0.0))
            for w in walls]
    segs += [((x, y, 0.0), (x, y, JAMB_HEIGHT_M)) for x, y in jambs]
    if not segs:
        return np.zeros((0, 2))
    R = np.asarray(frame.R, float)
    Km = np.asarray(frame.K, float)
    c = np.asarray(frame.center, float)
    cam_xy = np.array(to_graph_xy(alignment, c))
    near = NEAR_PLANE_M / alignment.scale
    out = []
    for A, B in segs:
        a = R.T @ (np.array(from_graph_xyz(alignment, *A)) - c)
        b = R.T @ (np.array(from_graph_xyz(alignment, *B)) - c)
        if a[2] < near and b[2] < near:
            continue  # behind the camera
        t0, t1 = 0.0, 1.0
        if a[2] < near:
            t0 = (near - a[2]) / (b[2] - a[2])
        if b[2] < near:
            t1 = (near - a[2]) / (b[2] - a[2])
        a3, b3 = a + t0 * (b - a), a + t1 * (b - a)
        pa = (Km @ a3)[:2] / (Km @ a3)[2]
        pb = (Km @ b3)[:2] / (Km @ b3)[2]
        clip = _clip_to_image(pa, pb, width, height)
        if clip is None:
            continue
        s0, s1 = clip
        n = max(int(math.ceil(np.linalg.norm(pb - pa) * (s1 - s0) / SAMPLE_STEP_PX)), 1)
        s = np.linspace(s0, s1, n + 1)
        uv = pa + s[:, None] * (pb - pa)
        # perspective-correct parameter back on the 3D segment, then graph xy
        za, zb = a3[2], b3[2]
        t3 = t0 + (s * za / ((1 - s) * zb + s * za)) * (t1 - t0)
        q = np.asarray(A[:2]) + t3[:, None] * (np.asarray(B[:2]) - np.asarray(A[:2]))
        keep = ((uv[:, 0] >= 0) & (uv[:, 0] < width) & (uv[:, 1] >= 0) & (uv[:, 1] < height)
                & ~_occluded(cam_xy, q, walls))
        out.append(uv[keep])
    return np.vstack(out) if out else np.zeros((0, 2))


def _edge_alignment(graph: VenueGraph, sfm: SfmResult, alignment: Alignment,
                    video: PreparedVideo, heldout_t_s: Sequence[float]) -> tuple[float | None, float | None]:
    walls, jambs = _walls(graph), _jambs(graph)
    ts = np.array([f.t_s for f in sfm.frames], float)
    dists = []
    with tempfile.TemporaryDirectory(prefix="walktwin-geom-") as tmp:
        for k, t in enumerate(heldout_t_s):
            if len(ts) == 0:
                break
            i = int(np.argmin(np.abs(ts - t)))
            if abs(ts[i] - t) > HELDOUT_MATCH_S:
                continue
            path = extract_frame(video.path, float(t), Path(tmp) / f"heldout_{k:04d}.jpg")
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            edges = cv2.Canny(img, CANNY_LOW, CANNY_HIGH)
            if not edges.any():
                continue  # no image edges: nothing to measure against
            dt = cv2.distanceTransform(255 - edges, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
            uv = _model_samples(sfm.frames[i], alignment, walls, jambs, img.shape[1], img.shape[0])
            if len(uv) == 0:
                continue
            j = np.floor(uv).astype(int)
            dists.append(dt[j[:, 1], j[:, 0]])
    if not dists:
        return None, None
    d = np.concatenate(dists)
    return float(d.mean()), float((d <= EDGE_WITHIN_PX).mean())


# ----------------------------------------------------------------------- public


def select_heldout_t_s(sfm: SfmResult, graph: VenueGraph) -> list[float]:
    """SfM frame times more than HELDOUT_MIN_GAP_S from every keyframe (never critiqued)."""
    kts = np.array([k.t_s for k in graph.keyframes], float)
    out = []
    for f in sorted(sfm.frames, key=lambda f: f.t_s):
        if len(kts) == 0 or np.abs(kts - f.t_s).min() > HELDOUT_MIN_GAP_S:
            out.append(float(f.t_s))
    return out


def score_geometry(graph: VenueGraph, sfm: SfmResult, alignment: Alignment,
                   video: PreparedVideo | None = None,
                   heldout_t_s: list[float] = []) -> GeometryScore:  # noqa: B006 - never mutated
    """Measure the graph against the walker's SfM path, points and held-out frames."""
    frames = sorted(sfm.frames, key=lambda f: f.t_s)
    xy = np.array([to_graph_xy(alignment, f.center) for f in frames], float).reshape(-1, 2)
    support, unexplained = _point_scores(graph, sfm, alignment)
    chamfer = within = None
    if video is not None and heldout_t_s:
        chamfer, within = _edge_alignment(graph, sfm, alignment, video, heldout_t_s)
    return GeometryScore(
        alignment_hash=alignment.hash,
        illegal_crossings=_crossings(graph, frames, xy),
        wall_support=support,
        unexplained_points=unexplained,
        edge_chamfer_px=chamfer,
        edge_within_5px=within,
        heldout_t_s=[float(t) for t in heldout_t_s],
    )


def is_regression(before: GeometryScore, after: GeometryScore) -> bool:
    """True if `after` measures worse than `before`. Scores under different
    alignments are not comparable: ValueError."""
    if before.alignment_hash != after.alignment_hash:
        raise ValueError("alignment_mismatch: scores were measured under different alignments")
    if len(after.illegal_crossings) > len(before.illegal_crossings):
        return True
    if after.wall_support < before.wall_support - REGRESSION_WALL_SUPPORT:
        return True
    if (before.edge_within_5px is not None and after.edge_within_5px is not None
            and after.edge_within_5px < before.edge_within_5px - REGRESSION_EDGE_WITHIN):
        return True
    return False
