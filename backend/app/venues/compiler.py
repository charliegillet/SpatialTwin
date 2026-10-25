"""Deterministic compiler: a VenueDraftV1 (what Gemini read off a floor plan) -> a strict VenueV2.

Nothing a model returns reaches the planner except through this module, ``graph_checks`` and an operator's Accept.
The compiler is therefore plain geometry and declared defaults, with no model call and no randomness: the same
draft, image size and options always give the same venue and the same ``geometry_revision``.

What is *measured* vs *assumed* (see docs/plans/contracts/compiler.md for the table):
  * measured from the drawing: the relative layout (which room is where, which walls are shared), where doors
    and exits sit along a wall, and the room names;
  * taken from the operator or a reference on the drawing: the metre scale (priority: operator width > the
    draft's scale reference > a declared default building width per image kind);
  * assumed (declared rates, listed in ``CompileReport.defaults`` and in the venue provenance): door and exit
    widths the drawing did not give, throughput and service rates, capacities, occupants, the horizon.

Coordinate transform (also used, inverted, by ``ai/real2sim/overlay.py``):
  pixel      x_px = x/1000 * width_px,  y_px = y/1000 * height_px          (image y grows down)
  bbox       minx_px, maxy_px = west-most / south-most edge over every room box (and extra box)
  metres     X = (x_px - minx_px) * metres_per_px,  Y = (maxy_px - y_px) * metres_per_px
so the venue origin is the south-west corner of the drawn building and Y grows north. Snapping pins the
south-west-most grid line to 0, which keeps this affine map exact (no hidden shift) for the overlay.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from pydantic import ValidationError

from backend.app.ai.real2sim.schema import CompileReport, CompileResult, DraftDoor, DraftRoom, \
    SourceImage, VenueDraftV1
from backend.app.venues.model import VenueV2, load_building_v2, point_in_polygon

# ---- declared defaults (documented in docs/plans/contracts/compiler.md) -----------------------------------------
GRID_M = 0.1                       # every coordinate is rounded to 0.1 m
SNAP_MIN_M, SNAP_FRACTION = 0.4, 0.015   # cluster tolerance: max(0.4 m, 1.5 % of the axis extent)
DEFAULT_BUILDING_WIDTH_M = {"evacuation_map": 30.0, "architectural_plan": 20.0, "sketch": 12.0,
                            "photo_of_plan": 20.0, "video_walkthrough": 10.0, "other": 20.0}
DEFAULT_DOOR_M, DEFAULT_WINDOW_M = 0.9, 0.6
MIN_OPENING_M = 0.6                # graph_checks flags openings outside 0.6-6.0 m
MAX_OPENING_M = 6.0
DOOR_THROUGHPUT_PER_M = 1.0        # people per second per metre of door width (building-v2: 3.0 m -> 3.0 p/s)
EXIT_SERVICE_PER_M = 0.6           # building-v2: 3.0 m -> 2.0, 2.4 m -> 1.5, 1.8 m -> 1.0
WINDOW_SERVICE_PER_M = 0.3         # an escape window is slower than a door
TRAVEL_TIME_S = 2                  # one solver step (the venue time step)
TIME_STEP_S = 2
CAPACITY_PER_M2 = 1.0              # building-v2 holds at most about one person per m²
MIN_CAPACITY = 2
CIRCULATION = frozenset({"corridor", "lobby", "stair"})    # no occupants are placed here by default
DEFAULT_DENSITY = {"evacuation_map": 0.08, "architectural_plan": 0.08, "sketch": 0.12,
                   "photo_of_plan": 0.10, "video_walkthrough": 0.10, "other": 0.10}   # people per m² of non-circulation floor
LED_PIXELS_PER_ELEMENT = 3
MIN_HORIZON_S, MAX_HORIZON_S = 30, 120
WALK_SPEED_M_PER_S = 1.6           # horizon = (width + height) / 1.6 s plus queueing time, see _horizon
MAX_FREE_DOORS = 3
# An exit stair with no outside wall (an upper floor's stair core) is a way down inside its room, not a wall
# opening. Only circulation space can hold one: a "stair" inside an office or a bedroom is a misreading.
INTERIOR_STAIR_ROOMS = frozenset({"stair", "lobby", "corridor"})
STAIR_CLEARANCE_M = 0.5            # the drawn or label point must sit this far inside every wall of the room
EPS = 1e-9

Rect = Tuple[float, float, float, float]            # x0, y0, x1, y1 in metres, y0 < y1
Segment = Tuple[str, float, float, float]           # axis ("h"|"v"), at, lo, hi


def _r1(value: float) -> float:
    return round(round(value / GRID_M) * GRID_M, 1)


# ---- transform -------------------------------------------------------------------------------------------------
class _Frame:
    """The affine pixel <-> metre map of one compile (inverse of what the overlay draws)."""

    def __init__(self, image: SourceImage, draft: VenueDraftV1):
        self.image = image
        boxes = [box for room in draft.rooms for box in [room.box, *room.extra_boxes]]
        self.minx_px = min(b[1] for b in boxes) / 1000 * image.width_px
        self.maxx_px = max(b[3] for b in boxes) / 1000 * image.width_px
        self.miny_px = min(b[0] for b in boxes) / 1000 * image.height_px
        self.maxy_px = max(b[2] for b in boxes) / 1000 * image.height_px
        self.mpp = 0.0

    def px(self, y: float, x: float) -> Tuple[float, float]:
        return x / 1000 * self.image.width_px, y / 1000 * self.image.height_px

    def to_m(self, y: float, x: float) -> Tuple[float, float]:
        x_px, y_px = self.px(y, x)
        return (x_px - self.minx_px) * self.mpp, (self.maxy_px - y_px) * self.mpp


# ---- snapping --------------------------------------------------------------------------------------------------
def _cluster(values: Sequence[float], tol: float) -> Tuple[Dict[float, float], List[Tuple[List[float], float]]]:
    """Single-linkage clusters of 1-D coordinates (gap <= tol, span <= 2*tol); the lowest cluster is pinned to 0
    when it holds the frame origin. A void drawn along the west or south edge frames the building but is not a
    room, so the rooms then start east or north of 0 and keep that offset (no hidden shift against the overlay)."""
    clusters: List[List[float]] = []
    for value in sorted(set(values)):
        if clusters and value - clusters[-1][-1] <= tol and value - clusters[-1][0] <= 2 * tol:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    reps: List[float] = []
    groups: List[List[List[float]]] = []
    for i, cluster in enumerate(clusters):
        rep = 0.0 if i == 0 and cluster[0] <= tol else _r1(sum(cluster) / len(cluster))
        if reps and rep <= reps[-1] + GRID_M / 2:        # two clusters rounding to one grid line: merge them
            groups[-1].append(cluster)
            continue
        reps.append(rep)
        groups.append([cluster])
    mapping: Dict[float, float] = {}
    detail: List[Tuple[List[float], float]] = []
    for rep, members in zip(reps, groups):
        flat = [v for c in members for v in c]
        for value in flat:
            mapping[value] = rep
        detail.append((flat, rep))
    return mapping, detail


# ---- rectilinear geometry --------------------------------------------------------------------------------------
def _union_outline(rects: Sequence[Rect]) -> List[Tuple[float, float]]:
    """Outline (counter-clockwise, starting at the lowest-then-leftmost vertex) of a connected union of rectangles."""
    xs = sorted({v for r in rects for v in (r[0], r[2])})
    ys = sorted({v for r in rects for v in (r[1], r[3])})
    filled = {(i, j) for i in range(len(xs) - 1) for j in range(len(ys) - 1)
              if any(r[0] <= xs[i] + EPS and xs[i + 1] <= r[2] + EPS and r[1] <= ys[j] + EPS and ys[j + 1] <= r[3] + EPS
                     for r in rects)}
    edges: Dict[Tuple[float, float], List[Tuple[float, float]]] = {}

    def add(a, b):
        edges.setdefault(a, []).append(b)

    for (i, j) in sorted(filled):
        if (i, j - 1) not in filled:
            add((xs[i], ys[j]), (xs[i + 1], ys[j]))
        if (i + 1, j) not in filled:
            add((xs[i + 1], ys[j]), (xs[i + 1], ys[j + 1]))
        if (i, j + 1) not in filled:
            add((xs[i + 1], ys[j + 1]), (xs[i], ys[j + 1]))
        if (i - 1, j) not in filled:
            add((xs[i], ys[j + 1]), (xs[i], ys[j]))
    loops: List[List[Tuple[float, float]]] = []
    while any(edges.values()):
        start = min(p for p, out in edges.items() if out)
        loop, cur = [start], start
        while True:
            nxt = edges[cur].pop(0)
            if nxt == start:
                break
            loop.append(nxt)
            cur = nxt
        loops.append(loop)
    loop = max(loops, key=lambda l: abs(_area(l)))
    simple = [p for i, p in enumerate(loop)
              if not _collinear(loop[i - 1], p, loop[(i + 1) % len(loop)])]
    first = min(range(len(simple)), key=lambda i: (simple[i][1], simple[i][0]))
    return simple[first:] + simple[:first]


def _collinear(a, b, c) -> bool:
    return abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) < EPS


def _area(polygon: Sequence[Tuple[float, float]]) -> float:
    return sum(polygon[i][0] * polygon[(i + 1) % len(polygon)][1] - polygon[(i + 1) % len(polygon)][0] * polygon[i][1]
               for i in range(len(polygon))) / 2.0


def _connected(rects: Sequence[Rect]) -> List[int]:
    """Indices of rects connected (by positive-length contact) to rect 0."""
    def touch(a: Rect, b: Rect) -> bool:
        ox, oy = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
        return (ox > EPS and oy > -EPS) or (oy > EPS and ox > -EPS)
    seen, todo = {0}, [0]
    while todo:
        cur = todo.pop()
        for i, r in enumerate(rects):
            if i not in seen and touch(rects[cur], r):
                seen.add(i)
                todo.append(i)
    return sorted(seen)


def _segments(polygon: Sequence[Tuple[float, float]]) -> List[Segment]:
    out: List[Segment] = []
    for i, a in enumerate(polygon):
        b = polygon[(i + 1) % len(polygon)]
        if abs(a[1] - b[1]) < EPS:
            out.append(("h", a[1], min(a[0], b[0]), max(a[0], b[0])))
        elif abs(a[0] - b[0]) < EPS:
            out.append(("v", a[0], min(a[1], b[1]), max(a[1], b[1])))
    return out


def _shared(a: Sequence[Segment], b: Sequence[Segment]) -> List[Segment]:
    out: List[Segment] = []
    for ax, at, lo, hi in a:
        for bx, bt, blo, bhi in b:
            if ax == bx and abs(at - bt) < EPS:
                low, high = max(lo, blo), min(hi, bhi)
                if high - low > EPS:
                    out.append((ax, at, low, high))
    return sorted(set(out))


def _exterior(own: Sequence[Segment], others: Iterable[Sequence[Segment]]) -> List[Segment]:
    """Parts of ``own`` edges that no other room's edge covers: the building's outside wall."""
    cover = [seg for other in others for seg in other]
    out: List[Segment] = []
    for axis, at, lo, hi in own:
        spans = sorted((max(lo, l), min(hi, h)) for ax, t, l, h in cover
                       if ax == axis and abs(t - at) < EPS and min(hi, h) - max(lo, l) > EPS)
        cursor = lo
        for low, high in spans:
            if low - cursor > EPS:
                out.append((axis, at, cursor, low))
            cursor = max(cursor, high)
        if hi - cursor > EPS:
            out.append((axis, at, cursor, hi))
    return sorted(set(out))


def _nearest_segment(point: Tuple[float, float], segments: Sequence[Segment], min_len: float) -> Optional[Segment]:
    best, best_d = None, math.inf
    for seg in segments:
        axis, at, lo, hi = seg
        if hi - lo < min_len - EPS:
            continue
        px, py = point
        along, across = (px, py) if axis == "h" else (py, px)
        d = math.hypot(along - min(max(along, lo), hi), across - at)
        if d < best_d - EPS:
            best, best_d = seg, d
    return best


def _place(point: Tuple[float, float], seg: Segment, width: float) -> Tuple[Tuple[float, float], float]:
    """Project ``point`` on ``seg`` and clamp so a gap of ``width`` stays inside; shrinks the width if it cannot fit."""
    axis, at, lo, hi = seg
    width = round(min(width, hi - lo), 2)
    along = point[0] if axis == "h" else point[1]
    low = math.ceil((lo + width / 2) * 100 - 1e-6) / 100
    high = math.floor((hi - width / 2) * 100 + 1e-6) / 100
    along = round(min(max(along, low), high), 2) if low <= high else round((lo + hi) / 2, 2)
    return ((along, at) if axis == "h" else (at, along)), width


def _rect_segments(rect: Rect) -> List[Segment]:
    x0, y0, x1, y1 = rect
    return _segments([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _overlaps(a: Segment, b: Segment) -> bool:
    return a[0] == b[0] and abs(a[1] - b[1]) < EPS and min(a[3], b[3]) - max(a[2], b[2]) > EPS


def _snap_to_rooms(value: float, mapping: Dict[float, float], tol: float) -> float:
    """A coordinate that is not a room edge (a void's) onto the grid line of the nearest room edge within the
    snapping tolerance, so a void drawn against a wall shares that wall exactly; otherwise it is only rounded."""
    nearest = min(mapping, key=lambda raw: (abs(raw - value), raw))
    return mapping[nearest] if abs(nearest - value) <= tol else _r1(value)


def _wall_clearance(point: Tuple[float, float], polygon: Sequence[Tuple[float, float]]) -> float:
    """Distance from ``point`` to the nearest wall of a rectilinear room."""
    px, py = point
    best = math.inf
    for axis, at, lo, hi in _segments(polygon):
        along, across = (px, py) if axis == "h" else (py, px)
        best = min(best, math.hypot(along - min(max(along, lo), hi), across - at))
    return best


def _interior_point(candidates: Sequence[Tuple[str, Tuple[float, float], float]],
                    polygon: Sequence[Tuple[float, float]]) -> Optional[Tuple[str, Tuple[float, float]]]:
    """The first candidate (rounded to 1 cm) inside ``polygon`` at least its clearance from every wall."""
    for how, (x, y), clearance in candidates:
        point = (round(x, 2), round(y, 2))
        gap = _wall_clearance(point, polygon)
        if point_in_polygon(point[0], point[1], polygon) and gap > 1e-6 and gap >= clearance:
            return how, point
    return None


# ---- helpers ---------------------------------------------------------------------------------------------------
def _distribute(total: int, areas: Dict[str, float], caps: Dict[str, int]) -> Dict[str, int]:
    """Largest-remainder split of ``total`` over rooms by area, never above a room's cap."""
    placed = {k: 0 for k in areas}
    remaining = total
    for _ in range(len(areas) + 1):
        active = [k for k in sorted(areas) if placed[k] < caps[k]]
        if remaining <= 0 or not active:
            break
        weight = sum(areas[k] for k in active)
        quotas = {k: remaining * areas[k] / weight for k in active}
        take = {k: min(caps[k] - placed[k], int(quotas[k])) for k in active}
        left = remaining - sum(take.values())
        for k in sorted(active, key=lambda k: (-(quotas[k] - int(quotas[k])), k)):
            if left <= 0:
                break
            if placed[k] + take[k] < caps[k]:
                take[k] += 1
                left -= 1
        for k in active:
            placed[k] += take[k]
        remaining = total - sum(placed.values())
    return placed


def _horizon(extent: Tuple[float, float], occupants: int, service_total: float) -> int:
    walk = (extent[0] + extent[1]) / WALK_SPEED_M_PER_S
    queue = 1.25 * occupants / service_total if service_total > 0 else 0.0
    horizon = int(math.ceil((walk + queue) / TIME_STEP_S)) * TIME_STEP_S
    return max(MIN_HORIZON_S, min(MAX_HORIZON_S, horizon))


def _fmt(value: float) -> str:
    return f"{round(value, 2):g}"


def _canonical_revision(raw: dict) -> str:
    body = {k: v for k, v in raw.items() if k != "geometry_revision"}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "geom-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _appearance(draft: VenueDraftV1, rooms: Dict[str, DraftRoom], zone_id: Dict[str, str],
                polygons: Dict[str, List[Tuple[float, float]]], frame: _Frame, extent: Tuple[float, float],
                report: CompileReport) -> Optional[dict]:
    """Room colours and furniture (a video walkthrough's look), in venue metres. None when the draft has no look.

    Looks only: nothing here changes a zone, door, exit, rate or capacity. A piece is kept inside its room's bounding
    box so a misread position cannot float outside the building.
    """
    zones = {zone_id[k]: {"wall_color": r.wall_color, "floor_color": r.floor_color, "floor_material": r.floor_material}
             for k, r in rooms.items() if r.wall_color or r.floor_color or r.floor_material != "unknown"}
    furniture = []
    for piece in draft.furniture:
        if piece.room not in rooms:
            report.dropped.append(f"furniture {piece.label}: its room {piece.room} was dropped")
            continue
        xs = [p[0] for p in polygons[piece.room]]
        ys = [p[1] for p in polygons[piece.room]]
        x, y = frame.to_m(piece.point[0], piece.point[1])
        x = min(max(x, min(xs)), max(xs))
        y = min(max(y, min(ys)), max(ys))
        furniture.append({"id": f"F{len(furniture) + 1}", "zone": zone_id[piece.room], "label": piece.label,
                          "category": piece.category or "furniture", "position": [round(x, 2), round(y, 2)],
                          "width": round(piece.width_m, 2), "depth": round(piece.depth_m, 2),
                          "height": round(piece.height_m, 2), "yaw_deg": round(piece.yaw_deg, 1),
                          "color": piece.color})
    if not zones and not furniture:
        return None
    return {"zones": zones, "furniture": furniture}


def with_furniture(venue: VenueV2, furniture: Sequence[dict]) -> VenueV2:
    """The venue with its furniture replaced by an operator's edit (ids renumbered F1..), revision recomputed.

    Raises ValueError (or pydantic's ValidationError) when a piece is malformed or names an unknown zone.
    """
    raw = venue.to_json()
    zone_ids = {zone["id"] for zone in raw["zones"]}
    width, height = raw["extent"]
    pieces = []
    for index, piece in enumerate(furniture, 1):
        if piece.get("zone") not in zone_ids:
            raise ValueError("furniture names an unknown zone")
        x, y = piece["position"]
        pieces.append({**piece, "id": f"F{index}",
                       "position": [round(min(max(float(x), 0.0), width), 2), round(min(max(float(y), 0.0), height), 2)]})
    appearance = raw.get("appearance") or {"zones": {}}
    raw["appearance"] = {**appearance, "furniture": pieces}
    if not raw["appearance"]["zones"] and not pieces:
        raw.pop("appearance")
    probe = VenueV2.model_validate({**raw, "geometry_revision": "geom-pending"}).to_json()
    raw["geometry_revision"] = _canonical_revision(probe)
    return VenueV2.model_validate(raw)


# ---- the compiler ----------------------------------------------------------------------------------------------
def compile_draft(draft: VenueDraftV1, image: SourceImage, *, venue_id: str,
                  controllable_doors: Iterable[str] = (), headcount: Optional[int] = None,
                  building_width_m: Optional[float] = None,
                  name: Optional[str] = None, provenance: Optional[str] = None) -> CompileResult:
    """Compile a draft into a VenueV2. ``error`` is set only when no venue can be built (no room or no exit survives).

    Unknown ``controllable_doors`` keys are reported in ``dropped`` and ignored; more than three are kept and
    reported by graph_checks (``too_many_controllable_doors``), so the operator sees why Accept is blocked.
    """
    report = CompileReport()
    frame = _Frame(image, draft)

    # Voids (open to below, atria, light wells, shafts) are drawn on the plan but are not floor. They still frame the
    # building (the scale and the overlay use the full drawing) but never become zones; openings into them are not
    # doors and an exit cannot be in one. A real evacuation map reads them this way, and without it they would be
    # unreachable "rooms" that block Accept. Their outlines are kept (in metres, below) for one purpose: a wall that
    # faces an atrium is not an outside wall, so no exit is placed on it.
    void_rooms = [room for room in draft.rooms if room.kind == "void"]
    voids = {room.key for room in void_rooms}
    if voids:
        for key in sorted(voids):
            report.edits.append(f"room {key}: open to below / void; kept out of the walkable floor")
        for door in draft.doors:
            if set(door.between) & voids:
                report.dropped.append(f"door {door.key}: opens onto a void")
        for exit_ in draft.exits:
            if exit_.room in voids:
                report.dropped.append(f"exit {exit_.key}: its room {exit_.room} is a void")
        draft = draft.model_copy(update={
            "rooms": [room for room in draft.rooms if room.kind != "void"],
            "doors": [door for door in draft.doors if not set(door.between) & voids],
            "exits": [exit_ for exit_ in draft.exits if exit_.room not in voids]})
        if not draft.rooms:
            return CompileResult(None, report, "no_room_survived")

    # -- scale: operator width > draft reference > declared default width ---------------------------------------
    bbox_w_px = frame.maxx_px - frame.minx_px
    bbox_h_px = frame.maxy_px - frame.miny_px
    if bbox_w_px <= 0 or bbox_h_px <= 0:
        return CompileResult(None, report, "empty_drawing")
    scale = draft.scale
    if building_width_m is not None and building_width_m > 0:
        frame.mpp = building_width_m / bbox_w_px
        report.scale_basis = "operator_input"
        report.edits.append(f"scale: operator set the building width to {_fmt(building_width_m)} m")
    else:
        ref_mpp = None
        if scale.a is not None and scale.b is not None and scale.metres is not None:
            (ax, ay), (bx, by) = frame.px(scale.a[0], scale.a[1]), frame.px(scale.b[0], scale.b[1])
            dist = math.hypot(ax - bx, ay - by)
            candidate = scale.metres / dist if dist > 0 else 0.0
            if candidate and 3.0 <= candidate * bbox_w_px <= 300.0:
                ref_mpp = candidate
            else:
                report.dropped.append("scale reference: implied building width is outside 3-300 m; ignored")
        if ref_mpp:
            frame.mpp = ref_mpp
            report.scale_basis = scale.basis if scale.basis != "unknown" else "dimension_label"
            report.edits.append(f"scale: {_fmt(scale.metres)} m reference ({scale.basis}) gives the building "
                                f"width {_fmt(ref_mpp * bbox_w_px)} m")
        else:
            default_w = DEFAULT_BUILDING_WIDTH_M[draft.image_kind]
            frame.mpp = default_w / bbox_w_px
            report.scale_basis = "default_width"
            report.defaults.append(f"scale: no measured scale; assumed building width {_fmt(default_w)} m "
                                   f"(default for {draft.image_kind})")
    report.metres_per_px = frame.mpp

    # -- snap box edges to shared grid lines --------------------------------------------------------------------
    raw: Dict[str, List[Rect]] = {}
    for room in draft.rooms:
        rects = []
        for box in [room.box, *room.extra_boxes]:
            x0, y1 = frame.to_m(box[0], box[1])      # ymin, xmin -> north-west corner
            x1, y0 = frame.to_m(box[2], box[3])      # ymax, xmax -> south-east corner
            rects.append((x0, y0, x1, y1))
        raw[room.key] = rects
    all_x = [v for rs in raw.values() for r in rs for v in (r[0], r[2])]
    all_y = [v for rs in raw.values() for r in rs for v in (r[1], r[3])]
    tol_x = max(SNAP_MIN_M, SNAP_FRACTION * (max(all_x) - min(all_x)))
    tol_y = max(SNAP_MIN_M, SNAP_FRACTION * (max(all_y) - min(all_y)))
    map_x, groups_x = _cluster(all_x, tol_x)
    map_y, groups_y = _cluster(all_y, tol_y)
    for axis, groups in (("x", groups_x), ("y", groups_y)):
        for members, rep in groups:
            if len({round(m, 2) for m in members}) > 1:
                report.edits.append(f"snapped {len(members)} {axis} edges between {_fmt(round(min(members), 2))} and "
                                    f"{_fmt(round(max(members), 2))} m to {axis}={_fmt(rep)} m")
    report.edits.append(f"rounded every coordinate to {GRID_M} m")

    # -- rooms -> rectilinear polygons --------------------------------------------------------------------------
    rooms: Dict[str, DraftRoom] = {}
    polygons: Dict[str, List[Tuple[float, float]]] = {}
    # Drawn outlines that are not zones but are not outside either: voids, and extra boxes the compiler could not
    # attach to their room (still drawn floor). Exits never go on a wall facing one of them.
    not_outside: Dict[str, List[Segment]] = {}
    for room in draft.rooms:
        rects = [(map_x[r[0]], map_y[r[1]], map_x[r[2]], map_y[r[3]]) for r in raw[room.key]]
        if rects[0][2] - rects[0][0] < GRID_M / 2 or rects[0][3] - rects[0][1] < GRID_M / 2:
            report.dropped.append(f"room {room.key}: collapsed to nothing after snapping")
            continue
        kept = [rects[0]]
        for i, r in enumerate(rects[1:], 1):
            if r[2] - r[0] < GRID_M / 2 or r[3] - r[1] < GRID_M / 2:
                report.dropped.append(f"room {room.key}: extra box {i} collapsed after snapping")
            else:
                kept.append(r)
        if len(kept) > 1:
            linked = _connected(kept)
            for i in range(1, len(kept)):
                if i not in linked:
                    report.dropped.append(f"room {room.key}: extra box {i} does not touch the room; ignored")
                    not_outside[f"the unattached extra box {i} of {room.key}"] = _rect_segments(kept[i])
            kept = [kept[i] for i in linked]
            if len(kept) > 1:
                report.edits.append(f"room {room.key}: merged {len(kept)} boxes into one rectilinear outline")
        polygon = _union_outline(kept)
        rooms[room.key] = room
        polygons[room.key] = polygon
    if not rooms:
        return CompileResult(None, report, "no_room_survived")
    width_m = max(p[0] for poly in polygons.values() for p in poly)
    height_m = max(p[1] for poly in polygons.values() for p in poly)
    seg = {k: _segments(p) for k, p in polygons.items()}
    for room in void_rooms:
        for i, box in enumerate([room.box, *room.extra_boxes]):
            x0, y1 = frame.to_m(box[0], box[1])
            x1, y0 = frame.to_m(box[2], box[3])
            rect = (_snap_to_rooms(x0, map_x, tol_x), _snap_to_rooms(y0, map_y, tol_y),
                    _snap_to_rooms(x1, map_x, tol_x), _snap_to_rooms(y1, map_y, tol_y))
            if rect[2] - rect[0] > GRID_M / 2 and rect[3] - rect[1] > GRID_M / 2:
                not_outside[f"void {room.key}" + (f" (box {i})" if i else "")] = _rect_segments(rect)

    # -- ids -----------------------------------------------------------------------------------------------------
    reserved = {f"D{i}" for i in range(1, len(draft.doors) + 1)} | {f"E{i}" for i in range(1, len(draft.exits) + 1)}
    zone_id: Dict[str, str] = {}
    # A replacement must avoid generated ids and every other room's key too (rooms "D1" and "Z_D1" can coexist).
    taken = set(reserved) | set(rooms)
    for key in rooms:
        if key not in reserved:
            zone_id[key] = key
            continue
        candidate, n = f"Z_{key}", 2
        while candidate in taken:
            candidate, n = f"Z{n}_{key}", n + 1
        taken.add(candidate)
        zone_id[key] = candidate
        report.edits.append(f"room {key} renamed {candidate} (key collides with a door or exit id)")

    # -- doors ---------------------------------------------------------------------------------------------------
    wanted = list(dict.fromkeys(controllable_doors))
    draft_door_keys = {d.key for d in draft.doors}
    for key in wanted:
        if key not in draft_door_keys:
            report.dropped.append(f"controllable {key}: not a door in the draft; ignored")
    controllable = {k for k in wanted if k in draft_door_keys}

    placed_doors: List[dict] = []          # one per surviving room pair, in draft order
    by_pair: Dict[frozenset, dict] = {}
    for door in draft.doors:
        a, b = door.between
        if a not in rooms or b not in rooms:
            report.dropped.append(f"door {door.key}: joins a room that was dropped")
            continue
        point = frame.to_m(door.point[0], door.point[1])
        wall = _nearest_segment(point, _shared(seg[a], seg[b]), MIN_OPENING_M)
        if wall is None:
            report.dropped.append(f"door {door.key}: {a} and {b} share no wall long enough for a door; dropped")
            continue
        default_width = door.width_m is None
        want = door.width_m if door.width_m else DEFAULT_DOOR_M
        want = min(max(want, MIN_OPENING_M), MAX_OPENING_M)
        pos, width = _place(point, wall, want)
        if width < want - 1e-9:
            report.edits.append(f"door {door.key}: narrowed to {_fmt(width)} m to fit the shared wall")
        entry = {"keys": [door.key], "pair": (a, b), "wall": wall, "pos": pos, "width": width,
                 "draft": door, "symbols": [door.symbol], "defaulted": default_width}
        pair = frozenset((a, b))
        if pair in by_pair:
            first = by_pair[pair]
            same = first["wall"][:2] == wall[:2]
            total = first["width"] + width
            span = first["wall"][3] - first["wall"][2]
            merged_w = round(min(total, span, MAX_OPENING_M), 2)
            weight = (first["width"], width)
            if same:
                along_a = first["pos"][0] if wall[0] == "h" else first["pos"][1]
                along_b = pos[0] if wall[0] == "h" else pos[1]
                along = (along_a * weight[0] + along_b * weight[1]) / sum(weight)
            else:
                along = first["pos"][0] if first["wall"][0] == "h" else first["pos"][1]
            first["pos"], first["width"] = _place(((along, first["wall"][1]) if first["wall"][0] == "h"
                                                   else (first["wall"][1], along)), first["wall"], merged_w)
            first["keys"].append(door.key)
            first["symbols"].append(door.symbol)
            first["defaulted"] = first["defaulted"] and default_width
            report.edits.append(f"merged parallel doors {' and '.join(first['keys'])} between {a} and {b}: "
                                f"width {_fmt(first['width'])} m (the venue allows one door per room pair)")
            continue
        by_pair[pair] = entry
        placed_doors.append(entry)

    venue_doors: List[dict] = []
    for index, entry in enumerate(placed_doors, 1):
        did = f"D{index}"
        a, b = entry["pair"]
        door: DraftDoor = entry["draft"]
        free = any(k in controllable for k in entry["keys"])
        symbols = entry["symbols"]
        kind, actuation = "room_door", "indicator_only"
        if "fire_door" in symbols:
            kind, actuation = "fire_door", "hold_open"
        elif "opening" in symbols:
            kind, actuation = "opening", "fixed"
        note = None
        if free:
            kind, actuation = "servo_door", "motorized"
            note = "Marked controllable by the operator; simulated door, no physical gate."
        width = entry["width"]
        if entry["defaulted"]:
            report.defaults.append(f"door {door.key} ({did}) width {_fmt(width)} m (default; the drawing gave none)")
        for key in entry["keys"]:
            report.element_ids[key] = did
        report.evidence_points[did] = (door.point[0], door.point[1])
        record = {"id": did, "zones": [zone_id[a], zone_id[b]], "position": [entry["pos"][0], entry["pos"][1]],
                  "width": width, "throughput_per_sec": round(width * DOOR_THROUGHPUT_PER_M, 2),
                  "travel_time_seconds": TRAVEL_TIME_S, "default_state": "closed" if free else "open",
                  "kind": kind, "actuation": actuation, "planner_can_open": free}
        if note:
            record["note"] = note
        venue_doors.append(record)

    # -- exits ---------------------------------------------------------------------------------------------------
    venue_exits: List[dict] = []
    index = 0
    for ex in draft.exits:
        if ex.room not in rooms:
            report.dropped.append(f"exit {ex.key}: its room {ex.room} was dropped")
            continue
        room = rooms[ex.room]
        point = frame.to_m(ex.point[0], ex.point[1])
        # An exit the drawing marks as a stair is the way down inside the floor, never a wall opening: on an upper
        # floor a stair drawn as a facade door would be an exit into the air, and on a shared wall it would cut into
        # the next room. Door and window exits look for an outside wall first.
        stair_exit = ex.kind == "stair"
        wall = None
        if not stair_exit:
            neighbours = [seg[k] for k in rooms if k != ex.room]
            wall = _nearest_segment(point, _exterior(seg[ex.room], neighbours + list(not_outside.values())),
                                    MIN_OPENING_M)
            naive = _nearest_segment(point, _exterior(seg[ex.room], neighbours), MIN_OPENING_M)
            if naive is not None and naive != wall:
                facing = [what for what, outline in not_outside.items()
                          if any(_overlaps(naive, s) for s in outline)]
                if facing:
                    report.edits.append(f"exit {ex.key}: the wall of {ex.room} nearest its point faces "
                                        f"{', '.join(facing)} (drawn, not outside); not used as an outside wall")
        window = ex.kind == "window"
        default_width = ex.width_m is None
        want = ex.width_m if ex.width_m else (DEFAULT_WINDOW_M if window else DEFAULT_DOOR_M)
        want = min(max(want, MIN_OPENING_M), MAX_OPENING_M)
        # A door or window exit in a stair room with no outside wall is that stair core's way out: also inside.
        interior = stair_exit or (wall is None and room.kind == "stair")
        if interior:
            if room.kind not in INTERIOR_STAIR_ROOMS:
                report.dropped.append(f"exit {ex.key}: an exit stair in {ex.room} ({room.kind}); an interior exit "
                                      f"stair must be in a stair, lobby or corridor; dropped")
                continue
            polygon = polygons[ex.room]
            xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
            found = _interior_point([
                ("drawn point", point, STAIR_CLEARANCE_M),
                ("room label point", frame.to_m(room.label_point[0], room.label_point[1]), STAIR_CLEARANCE_M),
                ("room centre", ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2), 0.0)], polygon)
            if found is None:
                report.dropped.append(f"exit {ex.key}: no point inside {ex.room} clear of its walls for the interior "
                                      f"exit stair; dropped")
                continue
            how, pos = found
            width = want
            why = "exit stair" if stair_exit else "stair room with no outside wall"
            report.edits.append(f"exit {ex.key}: {why}; placed inside {ex.room} at ({_fmt(pos[0])}, "
                                f"{_fmt(pos[1])}) m ({how}), not in a wall")
        elif wall is None:
            report.dropped.append(f"exit {ex.key}: {ex.room} has no outside wall long enough for an exit; dropped")
            continue
        else:
            pos, width = _place(point, wall, want)
            if width < want - 1e-9:
                report.edits.append(f"exit {ex.key}: narrowed to {_fmt(width)} m to fit the outside wall")
        index += 1
        eid = f"E{index}"
        if default_width:
            report.defaults.append(f"exit {ex.key} ({eid}) width {_fmt(width)} m (default; the drawing gave none)")
        report.element_ids[ex.key] = eid
        report.evidence_points[eid] = (ex.point[0], ex.point[1])
        per_m = WINDOW_SERVICE_PER_M if window else EXIT_SERVICE_PER_M
        # Signs label every exit "EXIT"; announcements need to tell them apart, so a bare label names the exit after
        # its room ("North Exit Stair") instead.
        printed = ex.label.strip()
        generic = printed.upper().rstrip(".!") in ("", "EXIT", "EXITS", "EMERGENCY EXIT", "FIRE EXIT", "STAIR", "STAIRS",
                                                   "EXIT STAIR", "STAIRWAY")
        label = printed if not generic else ("Escape window" if window else
                                             room.name if "exit" in room.name.lower() else f"{room.name} exit")
        # "stair" means exactly this: inside its room, not in a wall (graph_checks and the 3D walls rely on it).
        venue_exits.append({"id": eid, "zone": zone_id[ex.room], "name": label, "position": [pos[0], pos[1]],
                            "width": width, "service_rate_per_sec": round(width * per_m, 2),
                            "kind": "stair" if interior else ("window" if window else "door")})
    if not venue_exits:
        return CompileResult(None, report, "no_exit_survived")
    for key in rooms:
        report.element_ids[key] = zone_id[key]
        report.evidence_points[zone_id[key]] = (rooms[key].label_point[0], rooms[key].label_point[1])

    # -- capacity and occupants ----------------------------------------------------------------------------------
    area = {k: abs(_area(p)) for k, p in polygons.items()}
    cap = {k: max(MIN_CAPACITY, int(math.floor(area[k] * CAPACITY_PER_M2 + 1e-9))) for k in rooms}
    living = [k for k in rooms if rooms[k].kind not in CIRCULATION] or list(rooms)
    occupants = {k: 0 for k in rooms}
    if headcount is not None:
        total = max(0, int(headcount))
        occupants.update(_distribute(total, {k: area[k] for k in living}, {k: cap[k] for k in living}))
        spill = [k for k in rooms if k not in living]
        short = total - sum(occupants.values())
        if short > 0 and spill:       # non-circulation rooms are full: overflow into corridors rather than lose people
            occupants.update(_distribute(short, {k: area[k] for k in spill}, {k: cap[k] for k in spill}))
        placed = sum(occupants.values())
        report.edits.append(f"headcount {total} distributed by floor area over {len(living)} rooms")
        if placed < total:
            report.edits.append(f"headcount capped: only {placed} of {total} fit under the room capacities")
    elif any(r.occupants_hint is not None for r in rooms.values()):
        # An explicit 0 is a reading ("this room is empty"), not a missing value.
        for k, room in rooms.items():
            hint = room.occupants_hint or 0
            occupants[k] = min(hint, cap[k])
            if hint > cap[k]:
                report.edits.append(f"room {k}: occupants hint {hint} capped to capacity {cap[k]}")
        report.defaults.append("occupants: taken from the per-room hints read off the drawing")
    else:
        density = DEFAULT_DENSITY[draft.image_kind]
        total = max(1, int(round(sum(area[k] for k in living) * density)))
        occupants.update(_distribute(total, {k: area[k] for k in living}, {k: cap[k] for k in living}))
        report.defaults.append(f"occupants: {sum(occupants.values())} people, declared {density} per m² of "
                               f"non-circulation floor ({draft.image_kind}); set a headcount to change it")
    total_people = sum(occupants.values())

    # -- assemble ------------------------------------------------------------------------------------------------
    extent = (_r1(width_m), _r1(height_m))
    horizon = _horizon(extent, total_people, sum(e["service_rate_per_sec"] for e in venue_exits))
    report.defaults.extend([
        f"door throughput {DOOR_THROUGHPUT_PER_M} people/s per metre of width; travel {TRAVEL_TIME_S} s (one step)",
        f"exit service rate {EXIT_SERVICE_PER_M} people/s per metre ({WINDOW_SERVICE_PER_M} for windows)",
        f"capacity {CAPACITY_PER_M2} person per m² of floor (minimum {MIN_CAPACITY})",
        f"time step {TIME_STEP_S} s; horizon {horizon} s sized to the building and the queue",
    ])
    led_map: Dict[str, Tuple[int, int]] = {}
    cursor = 0
    free_ids = [d["id"] for d in venue_doors if d["planner_can_open"] and d["default_state"] == "closed"]
    for element in [e["id"] for e in venue_exits] + free_ids:
        led_map[element] = (cursor, cursor + LED_PIXELS_PER_ELEMENT - 1)
        cursor += LED_PIXELS_PER_ELEMENT

    kinds = draft.image_kind.replace("_", " ")
    label = f"{name}: " if name else ""
    text = provenance or (
        f"{label}Compiled by the local compiler from a {kinds} read by Gemini 4 Argon; operator-accepted; declared rates "
        f"(scale: {report.scale_basis.replace('_', ' ')}; door {DOOR_THROUGHPUT_PER_M} p/s per m, exit "
        f"{EXIT_SERVICE_PER_M} p/s per m, {CAPACITY_PER_M2} person per m²); not a surveyed plan.")
    raw_venue = {
        "schema_version": "2.0.0", "venue_id": venue_id, "geometry_revision": "geom-pending", "provenance": text,
        "units": "m", "extent": list(extent), "default_horizon_seconds": horizon, "time_step_seconds": TIME_STEP_S,
        "zones": [{"id": zone_id[k], "name": rooms[k].name, "max_capacity": cap[k], "initial_occupants": occupants[k],
                   "polygon": [[x, y] for x, y in polygons[k]]} for k in rooms],
        "doors": venue_doors, "exits": venue_exits,
        "led_map": {k: list(v) for k, v in led_map.items()},
        "hazard_defaults": {k: v.model_dump(exclude_none=True) for k, v in load_building_v2().hazard_defaults.items()},
    }
    appearance = _appearance(draft, rooms, zone_id, polygons, frame, extent, report)
    if appearance is not None:
        raw_venue["appearance"] = appearance
    try:
        probe = VenueV2.model_validate(raw_venue).to_json()
        raw_venue["geometry_revision"] = _canonical_revision(probe)
        venue = VenueV2.model_validate(raw_venue)
    except (ValidationError, ValueError) as exc:
        return CompileResult(None, report, f"invalid_venue: {str(exc).splitlines()[0][:120]}")
    return CompileResult(venue, report, None)
