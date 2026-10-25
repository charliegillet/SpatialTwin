"""Deterministic compiler: a RoomLab room reading (RoomDraft, metres) -> a strict VenueV2 the planner can use.

A video walkthrough is read exactly as the RoomLab branch reads it (``ai/real2sim/room``: same prompt, provider schema
and normalizer). That reading is one free-form floor in metres with floor voids, interior walls (shell, glass
partition, railing), openings on walls and furniture. The evacuation planner and its graph checks need rectilinear
rooms joined by doors on shared walls, with exits on outside walls, so this module (plain geometry, no model call,
deterministic) converts one into the other:

1. align: the reading is turned so its dominant wall direction lies on the x axis (a phone walkthrough is never
   square to the axes), then every coordinate is clustered and rounded to 0.1 m, which makes near-square walls exact;
2. floor: the floor polygon minus its voids, split along every interior wall that crosses it into rooms; a room with
   a void inside it is cut through the void (a zone has no holes); a room that still has a slanted wall is traced on a
   0.1 m grid so doors and exits can be cut into it;
3. openings: a door or passage on an interior wall whose two sides are different rooms becomes a door; one on the
   outer shell becomes an exit; windows, railings and glass partitions are kept as looks only;
4. people and rates: the declared defaults of ``compiler.py`` (capacity per m², density, door and exit rates).

Coordinates: RoomLab uses x right/east and z south/forward (three.js axes); a venue uses x east and y north. After
the turn by ``theta`` (x' = x cos t + z sin t, z' = -x sin t + z cos t, which is three.js rotation.y = t), a venue point
is (x' - min x', max z' - z'), so the twin draws the room exactly as RoomLab does, turned by ``theta``.
"""
from __future__ import annotations

import math
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import ValidationError
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import split, unary_union

from backend.app.ai.real2sim.room.contracts import RoomDraft, Wall
from backend.app.ai.real2sim.schema import CompileReport, CompileResult
from backend.app.venues.compiler import (
    CAPACITY_PER_M2,
    DEFAULT_DENSITY,
    DOOR_THROUGHPUT_PER_M,
    EXIT_SERVICE_PER_M,
    LED_PIXELS_PER_ELEMENT,
    MAX_OPENING_M,
    MIN_CAPACITY,
    MIN_OPENING_M,
    TIME_STEP_S,
    TRAVEL_TIME_S,
    _canonical_revision,
    _distribute,
    _horizon,
)
from backend.app.venues.model import VenueV2, load_building_v2

GRID_M = 0.1
SNAP_MIN_M, SNAP_FRACTION = 0.3, 0.02      # cluster tolerance: max(0.3 m, 2 % of the axis extent)
EXTEND_M = 0.35                            # interior walls are extended this far to reach the wall they meet
MIN_ROOM_M2 = 1.0                          # graph_checks refuses smaller rooms; slivers are folded away
SIDE_PROBE_M = 0.35                        # how far either side of a wall the door's two rooms are looked up
MAX_FEATURES = 100
Pt = Tuple[float, float]


def _r1(value: float) -> float:
    return round(round(value / GRID_M) * GRID_M, 1)


class _Frame:
    """RoomLab metres -> aligned, snapped venue metres."""

    def __init__(self, theta: float, scale: float):
        self.cos, self.sin, self.scale = math.cos(theta), math.sin(theta), scale
        self.map_x: Dict[float, float] = {}
        self.map_z: Dict[float, float] = {}
        self.min_x = 0.0
        self.max_z = 0.0

    def turn(self, p: Sequence[float]) -> Pt:
        x, z = p[0] * self.scale, p[1] * self.scale
        return (round(x * self.cos + z * self.sin, 4), round(-x * self.sin + z * self.cos, 4))

    def snap(self, p: Pt) -> Pt:
        return (self.map_x.get(p[0], _r1(p[0])), self.map_z.get(p[1], _r1(p[1])))

    def venue(self, p: Pt) -> Pt:
        return (round(p[0] - self.min_x, 2), round(self.max_z - p[1], 2))

    def point(self, raw: Sequence[float]) -> Pt:
        """A raw RoomLab point straight to venue metres (turned and offset, not snapped: furniture, features)."""
        x, z = self.turn(raw)
        return self.venue((x, z))


def _cluster(values: Sequence[float], tol: float) -> Dict[float, float]:
    """Single-linkage clusters of 1-D coordinates (gap <= tol, span <= 2*tol), each mapped to its mean on the grid."""
    clusters: List[List[float]] = []
    for value in sorted(set(values)):
        if clusters and value - clusters[-1][-1] <= tol and value - clusters[-1][0] <= 2 * tol:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return {value: _r1(sum(cluster) / len(cluster)) for cluster in clusters for value in cluster}


def _dominant_angle(walls: Iterable[Wall]) -> float:
    """Length-weighted mean wall direction modulo 90° (a circular mean of four times each wall's angle)."""
    sx = sy = 0.0
    for wall in walls:
        dx, dz = wall.end[0] - wall.start[0], wall.end[1] - wall.start[1]
        length = math.hypot(dx, dz)
        if length < 1e-6:
            continue
        angle = math.atan2(dz, dx)
        sx += length * math.cos(4 * angle)
        sy += length * math.sin(4 * angle)
    return math.atan2(sy, sx) / 4 if (sx or sy) else 0.0


def _polygons(geometry) -> List[Polygon]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    return [g for g in getattr(geometry, "geoms", []) if isinstance(g, Polygon)]


def _rectilinear(polygon: Polygon) -> bool:
    coords = list(polygon.exterior.coords)
    return all(abs(a[0] - b[0]) < 1e-6 or abs(a[1] - b[1]) < 1e-6 for a, b in zip(coords, coords[1:]))


def _cut_holes(polygon: Polygon, cuts: List[float]) -> List[Polygon]:
    """A zone has no holes: cut through each hole along a grid line (x through the hole's middle). The cut is open
    floor, not a wall: its x is added to ``cuts`` so the halves are joined by an open passage."""
    pending, out = [polygon], []
    while pending:
        piece = pending.pop()
        if not piece.interiors:
            out.append(piece)
            continue
        hole = Polygon(piece.interiors[0])
        x = _r1((hole.bounds[0] + hole.bounds[2]) / 2)
        _, miny, _, maxy = piece.bounds
        parts = _polygons(split(piece, LineString([(x, miny - 1), (x, maxy + 1)])))
        if len(parts) < 2:   # degenerate: drop the hole's ring rather than loop
            out.append(Polygon(piece.exterior))
            continue
        cuts.append(x)
        pending.extend(parts)
    return out


def _trace(pieces: List[Polygon]) -> List[Polygon]:
    """Pieces with slanted edges traced on the 0.1 m grid (cell centres decide), so every edge is axis-aligned."""
    if all(_rectilinear(p) for p in pieces):
        return pieces
    minx = min(p.bounds[0] for p in pieces)
    miny = min(p.bounds[1] for p in pieces)
    maxx = max(p.bounds[2] for p in pieces)
    maxy = max(p.bounds[3] for p in pieces)
    cells: List[List[Polygon]] = [[] for _ in pieces]
    nx, ny = int(math.ceil((maxx - minx) / GRID_M)), int(math.ceil((maxy - miny) / GRID_M))
    from shapely.prepared import prep
    prepared = [prep(p) for p in pieces]
    for i in range(nx):
        x0 = round(minx + i * GRID_M, 4)
        for j in range(ny):
            y0 = round(miny + j * GRID_M, 4)
            centre = Point(x0 + GRID_M / 2, y0 + GRID_M / 2)
            for k, test in enumerate(prepared):
                if test.contains(centre):
                    cells[k].append(box(x0, y0, x0 + GRID_M, y0 + GRID_M))
                    break
    traced: List[Polygon] = []
    for group in cells:
        traced.extend(_polygons(unary_union(group)))
    return traced


def _clean(polygon: Polygon) -> List[Pt]:
    """Exterior ring, counter-clockwise, rounded to 0.1 m, without the closing point or collinear vertices."""
    ring = polygon.exterior
    coords = [(_r1(x), _r1(y)) for x, y in (ring.coords if ring.is_ccw else list(ring.coords)[::-1])][:-1]
    out: List[Pt] = []
    for p in coords:
        if out and p == out[-1]:
            continue
        out.append(p)
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
            if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < 1e-9:
                del out[i]
                changed = True
                break
    return out


_NAME_HINTS = (
    (re.compile(r"counter|reception|desk|kiosk"), "Reception"),
    (re.compile(r"bed\b"), "Bedroom"),
    (re.compile(r"sofa|couch|lounge|armchair"), "Lounge"),
    (re.compile(r"stove|oven|fridge|kitchen|sink"), "Kitchen"),
    (re.compile(r"stair"), "Stair area"),
    (re.compile(r"toilet|shower|bath"), "Bathroom"),
)


def _zone_names(polys: List[Polygon], labels: List[List[str]], scene_name: str) -> List[str]:
    if len(polys) == 1:
        name = scene_name.strip() if scene_name and scene_name != "Estimated room" else "Room"
        return [name[:40]]
    names: List[str] = []
    cx = sum(p.centroid.x for p in polys) / len(polys)
    cy = sum(p.centroid.y for p in polys) / len(polys)
    for poly, words in zip(polys, labels):
        text = " ".join(words).lower()
        hint = next((name for pattern, name in _NAME_HINTS if pattern.search(text)), None)
        if hint is None:
            dx, dy = poly.centroid.x - cx, poly.centroid.y - cy
            side = ("East" if dx > 0 else "West") if abs(dx) >= abs(dy) else ("North" if dy > 0 else "South")
            hint = f"{side} area"
        names.append(hint)
    seen: Dict[str, int] = {}
    for i, name in enumerate(names):
        if names.count(name) > 1:
            seen[name] = seen.get(name, 0) + 1
            names[i] = f"{name} {seen[name]}"
    return names


def _zone_ids(names: List[str]) -> List[str]:
    ids: List[str] = []
    for name in names:
        base = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")[:24] or "ROOM"
        if re.fullmatch(r"[DEF][0-9]+", base):
            base = f"Z_{base}"
        candidate, n = base, 2
        while candidate in ids:
            candidate, n = f"{base}_{n}", n + 1
        ids.append(candidate)
    return ids


def _place_on(point: Pt, segments: List[Tuple[Pt, Pt]], want: float) -> Optional[Tuple[Pt, float]]:
    """The opening centred as near ``point`` as fits on the nearest axis-aligned segment, and its width."""
    best = None
    for a, b in segments:
        if abs(a[0] - b[0]) > 1e-6 and abs(a[1] - b[1]) > 1e-6:
            continue
        line = LineString([a, b])
        if line.length < MIN_OPENING_M - 1e-9:
            continue
        distance = line.distance(Point(point))
        if best is None or distance < best[0]:
            best = (distance, a, b)
    if best is None:
        return None
    _, a, b = best
    horizontal = abs(a[1] - b[1]) < 1e-6
    lo, hi = sorted((a[0], b[0]) if horizontal else (a[1], b[1]))
    width = round(min(max(want, MIN_OPENING_M), MAX_OPENING_M, hi - lo), 2)
    along = point[0] if horizontal else point[1]
    along = min(max(along, lo + width / 2), hi - width / 2)
    along = round(along, 2)
    return ((along, a[1]) if horizontal else (a[0], along)), width


def _shared(a: List[Pt], b: List[Pt]) -> List[Tuple[Pt, Pt]]:
    """Axis-aligned stretches of wall two zone outlines share."""
    out = []
    lines = LineString(a + [a[0]]).intersection(LineString(b + [b[0]]))
    for geom in getattr(lines, "geoms", [lines]):
        if isinstance(geom, LineString) and geom.length > 1e-6:
            coords = list(geom.coords)
            out.extend((tuple(map(lambda v: round(v, 4), p)), tuple(map(lambda v: round(v, 4), q)))
                       for p, q in zip(coords, coords[1:]))
    return out


def _outside(zone: List[Pt], others: List[List[Pt]]) -> List[Tuple[Pt, Pt]]:
    """Stretches of a zone's outline no other zone touches."""
    ring = LineString(zone + [zone[0]])
    for other in others:
        ring = ring.difference(LineString(other + [other[0]]))
    out = []
    for geom in getattr(ring, "geoms", [ring]):
        if isinstance(geom, LineString) and geom.length > 1e-6:
            coords = list(geom.coords)
            out.extend(((round(p[0], 4), round(p[1], 4)), (round(q[0], 4), round(q[1], 4)))
                       for p, q in zip(coords, coords[1:]))
    return out


def compile_room(room: RoomDraft, *, venue_id: str, controllable_doors: Iterable[str] = (),
                 headcount: Optional[int] = None, building_width_m: Optional[float] = None,
                 name: Optional[str] = None, provenance: Optional[str] = None) -> CompileResult:
    """Compile a RoomLab reading into a VenueV2. ``error`` is set only when no venue can be built."""
    report = CompileReport()
    walls = {wall.id: wall for wall in room.walls}
    shell = [wall for wall in room.walls if wall.id.startswith("wall-") and wall.role == "shell"]
    theta = _dominant_angle(shell or room.walls)

    # -- scale: operator width > the reading's own metres (a model estimate) --------------------------------------
    scale = 1.0
    turned_floor = [_Frame(theta, 1.0).turn(p) for p in room.floor]
    raw_width = max(p[0] for p in turned_floor) - min(p[0] for p in turned_floor)
    if building_width_m is not None and building_width_m > 0 and raw_width > 0:
        scale = building_width_m / raw_width
        report.scale_basis = "operator_input"
        report.edits.append(f"scale: operator set the building width to {building_width_m:g} m")
    else:
        report.scale_basis = "video_estimate"
        report.defaults.append("scale: metres as estimated by Gemini from the video (doors, ceilings, furniture)")
    report.metres_per_px = scale
    frame = _Frame(theta, scale)
    if abs(theta) > 1e-3:
        report.edits.append(f"turned the room {math.degrees(theta):.1f}° so its main walls lie on the plan axes")

    # -- snap every structural coordinate (floor, voids, interior walls) to shared grid lines ---------------------
    floor = [frame.turn(p) for p in room.floor]
    voids = [[frame.turn(p) for p in v.polygon] for v in room.floor_voids]
    interior = [w for w in room.walls if w not in shell]
    lines = [(w, frame.turn(w.start), frame.turn(w.end)) for w in interior]
    xs = [p[0] for p in floor] + [p[0] for v in voids for p in v] + [p[0] for _, a, b in lines for p in (a, b)]
    zs = [p[1] for p in floor] + [p[1] for v in voids for p in v] + [p[1] for _, a, b in lines for p in (a, b)]
    tol_x = max(SNAP_MIN_M, SNAP_FRACTION * (max(xs) - min(xs)))
    tol_z = max(SNAP_MIN_M, SNAP_FRACTION * (max(zs) - min(zs)))
    frame.map_x = _cluster(xs, tol_x)
    frame.map_z = _cluster(zs, tol_z)
    floor_s = [frame.snap(p) for p in floor]
    voids_s = [[frame.snap(p) for p in v] for v in voids]
    lines_s = [(w, frame.snap(a), frame.snap(b)) for w, a, b in lines]
    report.edits.append(f"snapped walls to shared lines and rounded every coordinate to {GRID_M} m")

    # -- floor: minus voids, split along interior walls -------------------------------------------------------------
    walkable = Polygon(floor_s).buffer(0)
    for i, void in enumerate(voids_s):
        if len(set(void)) >= 3:
            walkable = walkable.difference(Polygon(void).buffer(0))
            report.edits.append(f"floor void {room.floor_voids[i].id}: open to below; kept out of the walkable floor")
    pieces = _polygons(walkable)
    for wall, a, b in lines_s:
        if a == b:
            continue
        dx, dz = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dz)
        ux, uz = dx / length, dz / length
        cutter = LineString([(a[0] - ux * EXTEND_M, a[1] - uz * EXTEND_M), (b[0] + ux * EXTEND_M, b[1] + uz * EXTEND_M)])
        next_pieces: List[Polygon] = []
        for piece in pieces:
            parts = _polygons(split(piece, cutter)) if cutter.intersects(piece) else [piece]
            next_pieces.extend(parts)
        if len(next_pieces) > len(pieces):
            report.edits.append(f"{wall.role} {wall.id}: divides the floor into separate rooms")
        pieces = next_pieces
    holes_cut: List[Polygon] = []
    cuts: List[float] = []
    for piece in pieces:
        parts = _cut_holes(piece, cuts)
        if len(parts) > 1:
            report.edits.append("a room surrounding a void was cut through the void (a room has no holes)")
        holes_cut.extend(parts)
    pieces = [p for p in _trace(holes_cut) if p.area >= MIN_ROOM_M2]
    if len(pieces) < len(holes_cut):
        report.dropped.append(f"{len(holes_cut) - len(pieces)} floor sliver(s) under {MIN_ROOM_M2:g} m² left out")
    if not pieces:
        return CompileResult(None, report, "no_room_survived")
    if any(not _rectilinear(p) for p in holes_cut):
        report.edits.append(f"slanted walls traced on a {GRID_M} m grid so doors and exits can be placed")

    # -- venue frame: x east from the west-most wall, y north from the south-most wall ----------------------------
    frame.min_x = min(p.bounds[0] for p in pieces)
    frame.max_z = max(p.bounds[3] for p in pieces)
    zone_polys = [[frame.venue(p) for p in _clean(piece)] for piece in pieces]
    zone_polys = [[(_r1(x), _r1(y)) for x, y in poly] for poly in zone_polys]
    shapes = [Polygon(poly) for poly in zone_polys]
    labels: List[List[str]] = [[] for _ in shapes]
    for obj in room.objects:
        at = Point(frame.point(obj.center))
        for k, shape in enumerate(shapes):
            if shape.covers(at):
                labels[k].append(f"{obj.label} {obj.category}")
                break
    names = _zone_names(shapes, labels, room.name)
    zone_ids = _zone_ids(names)

    def zone_at(p: Pt) -> Optional[int]:
        point = Point(p)
        return next((k for k, shape in enumerate(shapes) if shape.covers(point)), None)

    # -- openings -----------------------------------------------------------------------------------------------
    doors: List[dict] = []
    exits: List[dict] = []
    by_pair: Dict[frozenset, dict] = {}
    features: List[dict] = []
    for opening in room.openings:
        wall = walls.get(opening.wall_id)
        if wall is None:
            report.dropped.append(f"opening {opening.id}: on an unknown wall")
            continue
        a, b = frame.snap(frame.turn(wall.start)), frame.snap(frame.turn(wall.end))
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length < 1e-6:
            report.dropped.append(f"opening {opening.id}: its wall collapsed after snapping")
            continue
        ux, uz = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        along = min(max(opening.offset_m * scale + opening.width_m * scale / 2, 0.0), length)
        centre_t = (a[0] + ux * along, a[1] + uz * along)
        centre = frame.venue(centre_t)
        width = opening.width_m * scale
        if opening.kind == "window":
            half = width / 2
            ends = (frame.venue((centre_t[0] - ux * half, centre_t[1] - uz * half)),
                    frame.venue((centre_t[0] + ux * half, centre_t[1] + uz * half)))
            features.append({"kind": "window", "a": list(ends[0]), "b": list(ends[1]),
                             "height": round(min(max(opening.height_m, 0.3), 4.0), 2),
                             "sill": round(min(opening.sill_m, 3.0), 2)})
            continue
        # The wall runs (ux, -uz) in venue axes (the turned z is flipped), so (uz, ux) is its normal.
        nx, ny = uz, ux
        probes = [(centre[0] + nx * SIDE_PROBE_M, centre[1] + ny * SIDE_PROBE_M),
                  (centre[0] - nx * SIDE_PROBE_M, centre[1] - ny * SIDE_PROBE_M)]
        if wall.role == "shell" and wall.id.startswith("wall-"):
            # The inside of the shell is whichever side lies in a room.
            k = next((zone_at(p) for p in probes if zone_at(p) is not None), None)
            if k is None:
                report.dropped.append(f"opening {opening.id}: no room behind it after voids were removed")
                continue
            others = [poly for j, poly in enumerate(zone_polys) if j != k]
            placed = _place_on(centre, _outside(zone_polys[k], others), width)
            if placed is None:
                report.dropped.append(f"opening {opening.id}: no outside wall long enough for an exit")
                continue
            pos, fit = placed
            exits.append({"key": opening.id, "zone": k, "position": pos, "width": fit})
            continue
        sides = {k for k in (zone_at(p) for p in probes) if k is not None}
        if len(sides) != 2:
            report.edits.append(f"opening {opening.id}: on a {wall.role} that does not separate two rooms; drawn only")
            continue
        i, j = sorted(sides)
        shared = _shared(zone_polys[i], zone_polys[j])
        placed = _place_on(centre, shared, width)
        if placed is None:
            report.dropped.append(f"opening {opening.id}: the two rooms share no wall long enough for a door")
            continue
        pos, fit = placed
        pair = frozenset((i, j))
        if pair in by_pair:
            first = by_pair[pair]
            report.edits.append(f"openings {first['key']} and {opening.id} join the same two rooms; kept the wider "
                                f"(the venue allows one door per room pair)")
            if fit > first["width"]:
                first.update(key=opening.id, position=pos, width=fit, kind=opening.kind)
            continue
        entry = {"key": opening.id, "pair": (i, j), "position": pos, "width": fit, "kind": opening.kind}
        by_pair[pair] = entry
        doors.append(entry)

    for wall, a, b in lines_s:
        if wall.role in ("railing", "partition") and a != b:
            features.append({"kind": "railing" if wall.role == "railing" else "glass", "a": list(frame.venue(a)),
                             "b": list(frame.venue(b)), "height": round(min(max(wall.height_m * scale, 0.5), 4.0), 2),
                             "sill": 0.0})

    # Cuts around a void are open floor: the two halves get the widest open passage their shared line allows.
    for x_cut in sorted(set(cuts)):
        xv = round(x_cut - frame.min_x, 1)
        for i in range(len(zone_polys)):
            for j in range(i + 1, len(zone_polys)):
                if frozenset((i, j)) in by_pair:
                    continue
                on_cut = [seg for seg in _shared(zone_polys[i], zone_polys[j])
                          if abs(seg[0][0] - xv) < 1e-6 and abs(seg[1][0] - xv) < 1e-6]
                if not on_cut:
                    continue
                a, b = max(on_cut, key=lambda seg: abs(seg[1][1] - seg[0][1]))
                placed = _place_on(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), [(a, b)], MAX_OPENING_M)
                if placed is None:
                    continue
                entry = {"key": f"void-cut-{len(by_pair) + 1}", "pair": (i, j), "position": placed[0],
                         "width": placed[1], "kind": "passage"}
                by_pair[frozenset((i, j))] = entry
                doors.append(entry)
                report.edits.append(f"open floor beside a void joined by a {placed[1]:g} m open passage (not a wall)")

    if not exits:
        report.dropped.append("no door or passage on an outside wall was read, so the room has no exit")
        return CompileResult(None, report, "no_exit_survived")

    # -- ids, doors and exits as venue records -------------------------------------------------------------------
    wanted = set(controllable_doors)
    venue_doors: List[dict] = []
    for index, entry in enumerate(doors, 1):
        did = f"D{index}"
        free = did in wanted
        kind, actuation = ("opening", "fixed") if entry["kind"] == "passage" else ("room_door", "indicator_only")
        record = {"id": did, "zones": [zone_ids[entry["pair"][0]], zone_ids[entry["pair"][1]]],
                  "position": [entry["position"][0], entry["position"][1]], "width": entry["width"],
                  "throughput_per_sec": round(entry["width"] * DOOR_THROUGHPUT_PER_M, 2),
                  "travel_time_seconds": TRAVEL_TIME_S, "default_state": "closed" if free else "open",
                  "kind": "servo_door" if free else kind, "actuation": "motorized" if free else actuation,
                  "planner_can_open": free}
        if free:
            record["note"] = "Marked controllable by the operator; simulated door, no physical gate."
        report.element_ids[entry["key"]] = did
        venue_doors.append(record)
    for key in sorted(wanted - {d["id"] for d in venue_doors}):
        report.dropped.append(f"controllable {key}: not a door in this reading; ignored")
    venue_exits: List[dict] = []
    for index, entry in enumerate(exits, 1):
        eid = f"E{index}"
        zone_name = names[entry["zone"]]
        x, y = entry["position"]
        extent_x = max(p[0] for poly in zone_polys for p in poly)
        extent_y = max(p[1] for poly in zone_polys for p in poly)
        side = ("west" if x <= 1e-6 else "east" if x >= extent_x - 1e-6 else
                "south" if y <= 1e-6 else "north" if y >= extent_y - 1e-6 else "outer")
        report.element_ids[entry["key"]] = eid
        venue_exits.append({"id": eid, "zone": zone_ids[entry["zone"]], "name": f"{zone_name} {side} exit",
                            "position": [x, y], "width": entry["width"],
                            "service_rate_per_sec": round(entry["width"] * EXIT_SERVICE_PER_M, 2), "kind": "door"})
    for k, zid in enumerate(zone_ids):
        report.element_ids[f"zone-{k + 1}"] = zid

    # -- capacity and occupants (the declared defaults of compiler.py) -------------------------------------------
    area = {zone_ids[k]: shapes[k].area for k in range(len(shapes))}
    cap = {z: max(MIN_CAPACITY, int(math.floor(area[z] * CAPACITY_PER_M2 + 1e-9))) for z in zone_ids}
    occupants = {z: 0 for z in zone_ids}
    if headcount is not None:
        total = max(0, int(headcount))
        occupants.update(_distribute(total, area, cap))
        report.edits.append(f"headcount {total} distributed by floor area over {len(zone_ids)} rooms")
        if sum(occupants.values()) < total:
            report.edits.append(f"headcount capped: only {sum(occupants.values())} of {total} fit under the room capacities")
    else:
        density = DEFAULT_DENSITY["video_walkthrough"]
        total = max(1, int(round(sum(area.values()) * density)))
        occupants.update(_distribute(total, area, cap))
        report.defaults.append(f"occupants: {sum(occupants.values())} people, declared {density} per m² of floor "
                               "(video walkthrough); set a headcount to change it")

    extent = (_r1(max(p[0] for poly in zone_polys for p in poly)), _r1(max(p[1] for poly in zone_polys for p in poly)))
    horizon = _horizon(extent, sum(occupants.values()), sum(e["service_rate_per_sec"] for e in venue_exits))
    report.defaults.extend([
        f"door throughput {DOOR_THROUGHPUT_PER_M} people/s per metre of width; travel {TRAVEL_TIME_S} s (one step)",
        f"exit service rate {EXIT_SERVICE_PER_M} people/s per metre",
        f"capacity {CAPACITY_PER_M2} person per m² of floor (minimum {MIN_CAPACITY})",
        f"time step {TIME_STEP_S} s; horizon {horizon} s sized to the space and the queue",
    ])
    led_map: Dict[str, List[int]] = {}
    cursor = 0
    for element in [e["id"] for e in venue_exits] + [d["id"] for d in venue_doors if d["planner_can_open"]]:
        led_map[element] = [cursor, cursor + LED_PIXELS_PER_ELEMENT - 1]
        cursor += LED_PIXELS_PER_ELEMENT

    # -- looks: room colours, furniture, railings, glass and windows ---------------------------------------------
    look = room.appearance
    zones_look = {}
    if look is not None and (look.wall_color or look.floor_color or look.floor_material != "unknown"):
        zones_look = {zid: {"wall_color": look.wall_color or "", "floor_color": look.floor_color or "",
                            "floor_material": look.floor_material} for zid in zone_ids}
    furniture = []
    for obj in room.objects:
        at = frame.point(obj.center)
        k = zone_at(at)
        if k is None:
            report.dropped.append(f"furniture {obj.label[:40]}: not on the walkable floor")
            continue
        yaw = ((obj.yaw_deg + math.degrees(theta) + 180.0) % 360.0) - 180.0
        furniture.append({"id": f"F{len(furniture) + 1}", "zone": zone_ids[k], "label": obj.label[:40],
                          "category": (obj.category or "furniture")[:24], "position": [round(at[0], 2), round(at[1], 2)],
                          "width": round(min(obj.width_m * scale, 10.0), 2), "depth": round(min(obj.depth_m * scale, 10.0), 2),
                          "height": round(min(obj.height_m, 4.0), 2), "yaw_deg": round(yaw, 1), "color": obj.color or ""})
        if len(furniture) >= 60:
            report.dropped.append("furniture beyond 60 pieces left out")
            break

    label = f"{name}: " if name else ""
    text = provenance or (
        f"{label}Compiled by the local compiler from a video walkthrough read by Gemini 4 Argon (RoomLab room "
        f"reading); operator-accepted; declared rates (scale: {report.scale_basis.replace('_', ' ')}; door "
        f"{DOOR_THROUGHPUT_PER_M} p/s per m, exit {EXIT_SERVICE_PER_M} p/s per m, {CAPACITY_PER_M2} person per m²); "
        "not a surveyed plan.")
    raw_venue = {
        "schema_version": "2.0.0", "venue_id": venue_id, "geometry_revision": "geom-pending", "provenance": text,
        "units": "m", "extent": list(extent), "default_horizon_seconds": horizon, "time_step_seconds": TIME_STEP_S,
        "zones": [{"id": zone_ids[k], "name": names[k], "max_capacity": cap[zone_ids[k]],
                   "initial_occupants": occupants[zone_ids[k]], "polygon": [list(p) for p in zone_polys[k]]}
                  for k in range(len(zone_ids))],
        "doors": venue_doors, "exits": venue_exits, "led_map": led_map,
        "hazard_defaults": {k: v.model_dump(exclude_none=True) for k, v in load_building_v2().hazard_defaults.items()},
        "appearance": {"zones": zones_look, "furniture": furniture, "features": features[:MAX_FEATURES]},
    }
    try:
        probe = VenueV2.model_validate(raw_venue).to_json()
        raw_venue["geometry_revision"] = _canonical_revision(probe)
        venue = VenueV2.model_validate(raw_venue)
    except (ValidationError, ValueError) as exc:
        return CompileResult(None, report, f"invalid_venue: {str(exc).splitlines()[0][:120]}")
    return CompileResult(venue, report, None)
