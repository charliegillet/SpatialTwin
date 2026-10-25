"""Geometry score: the separate, measured critic of a venue graph.

Nothing here asks a model anything. Three measurements against the SfM
reconstruction, through the alignment frozen on iteration 0:

- Illegal crossings. The walker cannot walk through a wall, so every time the
  SfM camera path (projected to graph xy) crosses a modelled wall away from a
  door is a timestamped error in the graph. A crossing needs the path to go
  from more than CROSSING_DEPTH_M on one side to more than it on the other
  (hysteresis), so SfM jitter at a wall is not a crossing. Leaving every zone
  is also an error, reported once per run of outside frames with edge
  "outside", unless the path leaves (and re-enters) through an exit door: a
  door with an "OUTSIDE" side, of any kind (Ruling R26). The test point is
  where the path actually leaves (enters) the zone rects: on the segment from
  the last frame strictly inside a rect to the next frame, which is outside
  every rect. Outside stretches split only by band frames (within OUTSIDE_M of
  a rect) are one run, so doorstep jitter is not a second exit.

  Known hysteresis limitation: a flip of confident side is located at the
  path's last sign change. A path that crosses the solid part of a wall into
  the depth band, slides along the band into a (padded) door gap and only then
  becomes confident on the far side is placed in the gap and not counted.
  Counting any sign change on the piece instead would flag legal wall-hugging
  walks through a door, which is worse, so the last-sign-change rule stays.
- Wall support / unexplained points. Of the SfM points in the wall-height band,
  the share near a modelled wall, and the share outside every zone.
- Edge alignment, held-out frames only: frames held out from the critique's
  frame pairs (the critique model may still have seen the whole video). The
  twin's floor-wall lines and door jambs are projected through the SfM poses
  and compared with Canny edges by a distance transform (chamfer). Samples
  hidden behind a modelled wall are culled from the chamfer but counted as
  misses: `edge_within_5px` is the share of projected samples within 5 px,
  culled samples counted as misses, so culling can never raise it.
  Appearance metrics (SSIM, LPIPS) are deliberately not used.

Walls are zone-rect edges minus door gaps (door position +/- mid width / 2).
Each door cuts only its nearest edge(s) within DOOR_ON_EDGE_M; edges tied
within DOOR_TIE_M are all cut when they are collinear and their joint span
contains the door (a door at the junction of two collinear edges), so a door
near a corner never cuts the perpendicular wall. Collinear overlapping edges of
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
DOOR_ON_EDGE_M = 0.5          # a door within this distance of its nearest rect edge cuts a gap in it
DOOR_TIE_M = 0.01             # edges this close to equally near share the door (junctions)
DOOR_TOLERANCE_M = 0.5        # crossings within this distance of a door gap are tolerated
CROSSING_DEPTH_M = 0.15       # a crossing goes from beyond this on one side to beyond it on the other
WALL_NEAR_M = 0.15            # "near a wall" for wall support
OUTSIDE_M = 0.15              # "outside every zone" beyond this distance from all rects
WALL_BAND_LOW_M = 0.5         # SfM points counted for wall support: this band above the floor
WALL_BAND_HIGH_M = 2.0
EDGE_WITHIN_PX = 5.0          # "aligned" edge sample
SAMPLE_STEP_PX = 5.0          # spacing of projected model samples
JAMB_HEIGHT_M = 2.0           # door jambs run 0 - 2.0 m at the gap ends
CANNY_LOW, CANNY_HIGH = 50, 150
HELDOUT_MIN_GAP_S = 1.0       # held-out frames are this far from every keyframe
MAX_HELDOUT_FRAMES = 24       # cost cap: at most this many held-out frames, evenly spread
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
    edge_within_5px: float | None  # share of projected samples within 5 px, culled samples counted as misses
    heldout_t_s: list[float] = field(default_factory=list)  # frames that contributed samples
    edge_samples_projected: int | None = None  # in front of the camera and inside the image
    edge_samples_kept: int | None = None       # of those, not hidden behind a modelled wall


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


def _along_across(e: _Edge, p: tuple[float, float]) -> tuple[float, float]:
    return (p[0], p[1]) if e.horizontal else (p[1], p[0])


def _edge_dist(e: _Edge, p: tuple[float, float]) -> float:
    along, across = _along_across(e, p)
    return math.hypot(max(e.lo - along, 0.0, along - e.hi), across - e.c)


_OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}


def _is_exterior_at(edges: list[_Edge], k: int, pos: tuple[float, float]) -> bool:
    """True if edge k is not shared at the door's along position: no other zone's
    collinear edge on the opposite side (a zone beyond the wall) covers it there.
    Same-side collinear edges (adjacent facade) do not make it interior."""
    e = edges[k]
    zone, side = e.name.split(".", 1)
    along = _along_across(e, pos)[0]
    return not any(o.name.split(".", 1)[1] == _OPPOSITE[side] and o.name.split(".", 1)[0] != zone
                   and abs(o.c - e.c) <= _COLLINEAR_EPS and o.lo <= along <= o.hi
                   for o in edges)


def _door_edges(edges: list[_Edge], pos: tuple[float, float], exit_door: bool = False) -> list[int]:
    """Indices of the edges a door at `pos` cuts: its nearest edge(s) within
    DOOR_ON_EDGE_M. An exit door (an "OUTSIDE" side) considers only exterior edges
    (not shared with another zone at the door) when any is within range, so it
    never cuts an interior partition. Ties (within DOOR_TIE_M) are grouped by
    line; a line is kept when the joint span of its tied edges contains the door
    strictly, so a door at the junction of two collinear edges cuts both but not
    the perpendicular wall ending there. If no tied line contains it, every tied
    edge is kept."""
    if not edges:
        return []
    dist = [_edge_dist(e, pos) for e in edges]
    pool = [k for k in range(len(edges)) if dist[k] <= DOOR_ON_EDGE_M]
    if exit_door:
        pool = [k for k in pool if _is_exterior_at(edges, k, pos)] or pool
    if not pool:
        return []
    best = min(dist[k] for k in pool)
    tied = [k for k in pool if dist[k] <= best + DOOR_TIE_M]
    lines: dict[tuple[bool, int], list[int]] = {}
    for k in tied:
        lines.setdefault((edges[k].horizontal, round(edges[k].c / _COLLINEAR_EPS)), []).append(k)
    keep = []
    for ks in lines.values():
        along = _along_across(edges[ks[0]], pos)[0]
        if min(edges[k].lo for k in ks) < along < max(edges[k].hi for k in ks):
            keep += ks
    return sorted(keep) if keep else tied


def _gaps_by_edge(graph: VenueGraph, edges: list[_Edge], pad: float,
                  doors=None) -> list[list[tuple[float, float]]]:
    """Per edge: along-edge gaps (position +/- mid width / 2 + pad) of the doors it carries."""
    gaps: list[list[tuple[float, float]]] = [[] for _ in edges]
    for d in graph.doors if doors is None else doors:
        half = (d.clear_width.low_m + d.clear_width.high_m) / 4 + pad
        for k in _door_edges(edges, d.position, exit_door="OUTSIDE" in (d.a, d.b)):
            along = _along_across(edges[k], d.position)[0]
            gaps[k].append((along - half, along + half))
    return gaps


def _walls(graph: VenueGraph, pad: float = 0.0) -> list[_Edge]:
    """Wall pieces: rect edges minus door gaps (widened by `pad`), shared edges once."""
    covered: dict[tuple[bool, float], list[tuple[float, float]]] = {}
    pieces = []
    edges = _rect_edges(graph)
    for e, gaps in zip(edges, _gaps_by_edge(graph, edges, pad)):
        key = (e.horizontal, round(e.c / _COLLINEAR_EPS))
        free = [(e.lo, e.hi)]
        for span in covered.get(key, []):
            free = _subtract(free, span)
        covered.setdefault(key, []).append((e.lo, e.hi))
        for gap in gaps:
            free = _subtract(free, gap)
        pieces += [_Edge(e.name, e.horizontal, e.c, lo, hi) for lo, hi in free if hi - lo > 1e-9]
    return pieces


def _jambs(graph: VenueGraph) -> list[tuple[float, float]]:
    """Graph xy of door gap ends that lie on their edge, deduplicated. A gap end
    beyond its edge (past a corner or a junction) is not a jamb."""
    seen, out = set(), []
    edges = _rect_edges(graph)
    for e, gaps in zip(edges, _gaps_by_edge(graph, edges, 0.0)):
        for a, b in gaps:
            for along in (a, b):
                if not (e.lo <= along <= e.hi):
                    continue
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


def _point_seg_dist(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    d = b - a
    L2 = float(d @ d)
    t = 0.0 if L2 == 0 else min(max(float((p - a) @ d) / L2, 0.0), 1.0)
    return float(np.linalg.norm(p - (a + t * d)))


def _exit_gaps(graph: VenueGraph) -> list[tuple[np.ndarray, np.ndarray]]:
    """Gap segments of exit doors (an "OUTSIDE" side, any kind: Ruling R26)."""
    exits = [d for d in graph.doors if "OUTSIDE" in (d.a, d.b)]
    edges = _rect_edges(graph)
    out = []
    for e, gaps in zip(edges, _gaps_by_edge(graph, edges, 0.0, doors=exits)):
        for a, b in gaps:
            if e.horizontal:
                out.append((np.array([a, e.c]), np.array([b, e.c])))
            else:
                out.append((np.array([e.c, a]), np.array([e.c, b])))
    return out


def _rect_interval(p0: np.ndarray, p1: np.ndarray, rect) -> tuple[float, float] | None:
    """Parameter range of p0 -> p1 inside the closed rect (Liang-Barsky)."""
    x, y, w, h = rect
    o = np.array([x, y])
    return _clip_to_box(p0 - o, p1 - o, w, h)


def _boundary_point(graph: VenueGraph, inside: np.ndarray, out: np.ndarray, leaving: bool) -> np.ndarray:
    """Where the segment inside -> out (inside strictly in a rect, out in none) leaves
    the union of rects; for re-entry (out -> inside) where it first enters it."""
    p0, p1 = (inside, out) if leaving else (out, inside)
    spans = [iv for z in graph.zones if (iv := _rect_interval(p0, p1, z.rect)) is not None]
    t = max(hi for _, hi in spans) if leaving else min(lo for lo, _ in spans)
    return p0 + t * (p1 - p0)


def _outside_crossings(graph: VenueGraph, t: np.ndarray, xy: np.ndarray, outside: np.ndarray) -> list[Crossing]:
    """One crossing per run: a maximal stretch of frames not strictly inside any
    rect that contains at least one outside frame (so outside stretches split only
    by band frames are one run). Excused when the path leaves, and re-enters if it
    comes back, through an exit door gap: the point where the segment from the last
    strict frame before the run to the run's first frame leaves the zone rects
    (re-entry: last run frame to the first strict frame after it, where it enters)
    must lie within DOOR_TOLERANCE_M of an exit gap. Reported at the run's first
    outside frame, with the midpoint time of the segment into it."""
    gaps = _exit_gaps(graph)
    strict = _dist_outside_rects(xy, graph) == 0.0
    n, out, i = len(t), [], 0

    def through_exit(inside: int, other: int, leaving: bool) -> bool:
        q = _boundary_point(graph, xy[inside], xy[other], leaving)
        return any(_point_seg_dist(q, g0, g1) <= DOOR_TOLERANCE_M for g0, g1 in gaps)

    while i < n:
        if strict[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and not strict[j + 1]:
            j += 1
        run = range(i, j + 1)
        first_out = next((k for k in run if outside[k]), None)
        if first_out is not None:
            checks = []
            if i > 0:
                checks.append(through_exit(i - 1, i, True))
            if j + 1 < n:
                checks.append(through_exit(j + 1, j, False))
            if not (checks and all(checks)):
                k = first_out
                t_s = (t[k - 1] + t[k]) / 2 if k > 0 else t[k]
                out.append(Crossing(t_s=float(t_s), x=float(xy[k, 0]), y=float(xy[k, 1]), edge="outside"))
        i = j + 1
    return out


def _wall_crossings(walls: list[_Edge], t: np.ndarray, xy: np.ndarray, outside: np.ndarray) -> list[Crossing]:
    """Hysteresis per wall piece: a crossing is a change of confident side (more
    than CROSSING_DEPTH_M from the wall line), located at the last actual sign
    change of the path in between and counted if that point lies on the piece.
    Outside frames break the chain (they are scored as "outside" runs)."""
    out = []
    for w in walls:
        d = (xy[:, 1] if w.horizontal else xy[:, 0]) - w.c
        side, last = None, None
        for m in range(len(t)):
            if outside[m]:
                side = last = None
                continue
            if abs(d[m]) <= CROSSING_DEPTH_M:
                continue  # within the depth band: keep the last confident side
            s = bool(d[m] > 0)
            if side is not None and s != side:
                for k in range(m - 1, last - 1, -1):
                    if (d[k] < 0) != (d[k + 1] < 0):
                        f = d[k] / (d[k] - d[k + 1])
                        q = xy[k] + f * (xy[k + 1] - xy[k])
                        along = q[0] if w.horizontal else q[1]
                        if w.lo <= along <= w.hi:
                            out.append(Crossing(t_s=float((t[k] + t[k + 1]) / 2), x=float(q[0]),
                                                y=float(q[1]), edge=w.name))
                        break
            side, last = s, m
    return out


def _crossings(graph: VenueGraph, frames: list[SfmFrame], xy: np.ndarray) -> list[Crossing]:
    if len(frames) == 0:
        return []
    t = np.array([f.t_s for f in frames], float)
    outside = _dist_outside_rects(xy, graph) > OUTSIDE_M
    out = (_outside_crossings(graph, t, xy, outside)
           + _wall_crossings(_walls(graph, pad=DOOR_TOLERANCE_M), t, xy, outside))
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


def _clip_to_box(a: np.ndarray, b: np.ndarray, w: float, h: float) -> tuple[float, float] | None:
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
    """The visible (not culled) samples of `_project_model`."""
    uv, visible = _project_model(frame, alignment, walls, jambs, width, height)
    return uv[visible]


def _project_model(frame: SfmFrame, alignment: Alignment, walls: list[_Edge],
                   jambs: list[tuple[float, float]], width: int,
                   height: int) -> tuple[np.ndarray, np.ndarray]:
    """Pixel samples (N, 2), every SAMPLE_STEP_PX, of the floor-wall lines and door
    jambs in front of the camera and inside the image, plus a mask of those not
    hidden behind a modelled wall. Pixel (i, j) covers [j, j+1) x [i, i+1) (COLMAP)."""
    segs = [((w.lo, w.c, 0.0), (w.hi, w.c, 0.0)) if w.horizontal else ((w.c, w.lo, 0.0), (w.c, w.hi, 0.0))
            for w in walls]
    segs += [((x, y, 0.0), (x, y, JAMB_HEIGHT_M)) for x, y in jambs]
    if not segs:
        return np.zeros((0, 2)), np.zeros(0, bool)
    R = np.asarray(frame.R, float)
    Km = np.asarray(frame.K, float)
    c = np.asarray(frame.center, float)
    cam_xy = np.array(to_graph_xy(alignment, c))
    near = NEAR_PLANE_M / alignment.scale
    out, vis = [], []
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
        clip = _clip_to_box(pa, pb, width, height)
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
        inside = (uv[:, 0] >= 0) & (uv[:, 0] < width) & (uv[:, 1] >= 0) & (uv[:, 1] < height)
        out.append(uv[inside])
        vis.append(~_occluded(cam_xy, q[inside], walls))
    if not out:
        return np.zeros((0, 2)), np.zeros(0, bool)
    return np.vstack(out), np.concatenate(vis)


@dataclass(frozen=True)
class _EdgeResult:
    chamfer_px: float | None
    within: float | None
    projected: int
    kept: int
    t_s: list[float]


def _stride(ts: Sequence[float], cap: int) -> list[float]:
    ts = list(ts)
    if len(ts) <= cap:
        return ts
    idx = np.unique(np.round(np.linspace(0, len(ts) - 1, cap)).astype(int))
    return [ts[i] for i in idx]


def _edge_alignment(graph: VenueGraph, sfm: SfmResult, alignment: Alignment,
                    video: PreparedVideo, heldout_t_s: Sequence[float]) -> _EdgeResult:
    walls, jambs = _walls(graph), _jambs(graph)
    ts = np.array([f.t_s for f in sfm.frames], float)
    kept_d, projected, used = [], 0, []
    with tempfile.TemporaryDirectory(prefix="walktwin-geom-") as tmp:
        for k, t in enumerate(_stride(heldout_t_s, MAX_HELDOUT_FRAMES)):
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
            uv, visible = _project_model(sfm.frames[i], alignment, walls, jambs, img.shape[1], img.shape[0])
            if len(uv) == 0:
                continue
            dt = cv2.distanceTransform(255 - edges, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
            j = np.floor(uv[visible]).astype(int)
            kept_d.append(dt[j[:, 1], j[:, 0]])
            projected += len(uv)
            used.append(float(t))
    if projected == 0:
        return _EdgeResult(None, None, 0, 0, [])
    d = np.concatenate(kept_d)
    chamfer = float(d.mean()) if len(d) else None
    # culled samples count as misses: the share is over every projected sample
    within = float((d <= EDGE_WITHIN_PX).sum() / projected)
    return _EdgeResult(chamfer, within, projected, len(d), used)


# ----------------------------------------------------------------------- public


def select_heldout_t_s(sfm: SfmResult, graph: VenueGraph) -> list[float]:
    """SfM frame times more than HELDOUT_MIN_GAP_S from every keyframe: frames held
    out from the critique's frame pairs."""
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
    edge = None
    if video is not None and heldout_t_s:
        edge = _edge_alignment(graph, sfm, alignment, video, heldout_t_s)
    return GeometryScore(
        alignment_hash=alignment.hash,
        illegal_crossings=_crossings(graph, frames, xy),
        wall_support=support,
        unexplained_points=unexplained,
        edge_chamfer_px=edge.chamfer_px if edge else None,
        edge_within_5px=edge.within if edge else None,
        heldout_t_s=edge.t_s if edge else [],
        edge_samples_projected=edge.projected if edge else None,
        edge_samples_kept=edge.kept if edge else None,
    )


def is_regression(before: GeometryScore, after: GeometryScore) -> bool:
    """True if `after` measures worse than `before`: more crossings, wall support
    down > 0.02, or edge_within_5px down > 0.05 or lost. Culling alone is not a
    regression (Ruling R32): edge_within_5px already counts culled samples as
    misses. Scores under different alignments are not comparable: ValueError."""
    if before.alignment_hash != after.alignment_hash:
        raise ValueError("alignment_mismatch: scores were measured under different alignments")
    if len(after.illegal_crossings) > len(before.illegal_crossings):
        return True
    if after.wall_support < before.wall_support - REGRESSION_WALL_SUPPORT:
        return True
    if before.edge_within_5px is not None:
        if after.edge_within_5px is None:
            return True  # the edge measurement was lost (e.g. everything culled)
        if after.edge_within_5px < before.edge_within_5px - REGRESSION_EDGE_WITHIN:
            return True
    return False
