"""Deterministic checks on a venue graph before an operator may accept it.

Gemini proposes the rooms, doors and exits; these checks decide whether the result can be planned and drawn.
Every issue is typed so the UI, the critique loop and the tests read the same codes. Errors block Accept;
warnings are shown next to the evidence.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

from backend.app.venues.model import VenueV2, point_in_polygon

Severity = Literal["error", "warning"]

# Mirrors frontend/src/twin/sceneModel.ts: walls only open where an opening lies exactly on an axis-aligned edge.
EPS = 1e-6
MAX_FREE_DOORS = 3
MAX_PLANNER_HORIZON = 120
MIN_OPENING_M, MAX_OPENING_M = 0.6, 6.0
# On-screen light strip bound; the compiler uses 3 pixels per exit and controllable door.
MAX_PIXELS = 96


@dataclass(frozen=True)
class GraphIssue:
    code: str
    severity: Severity
    message: str
    element_ids: Tuple[str, ...] = field(default_factory=tuple)

    def to_json(self) -> dict:
        data = asdict(self)
        data["element_ids"] = list(self.element_ids)
        return data


def _edges(polygon) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    return [(tuple(polygon[i]), tuple(polygon[(i + 1) % len(polygon)])) for i in range(len(polygon))]


def _on_axis_edge(point, a, b) -> bool:
    (px, py), (ax, ay), (bx, by) = point, a, b
    if abs(ay - by) < EPS and abs(py - ay) < EPS:
        return min(ax, bx) - EPS <= px <= max(ax, bx) + EPS
    if abs(ax - bx) < EPS and abs(px - ax) < EPS:
        return min(ay, by) - EPS <= py <= max(ay, by) + EPS
    return False


def _on_boundary(point, polygon) -> bool:
    return any(_on_axis_edge(point, a, b) for a, b in _edges(polygon))


def _polygon_area(polygon) -> float:
    return abs(sum(polygon[i][0] * polygon[(i + 1) % len(polygon)][1] - polygon[(i + 1) % len(polygon)][0] * polygon[i][1]
                   for i in range(len(polygon)))) / 2.0


def _strictly_inside(x: float, y: float, polygon) -> bool:
    """Even-odd test that excludes the boundary (point_in_polygon counts edges as inside)."""
    if _on_boundary((x, y), polygon):
        return False
    return point_in_polygon(x, y, polygon)


def check_venue(venue: VenueV2) -> List[GraphIssue]:
    issues: List[GraphIssue] = []
    zones = {z.id: z for z in venue.zones}

    # Geometry: rectilinear rooms, so the 3D walls and door gaps line up.
    for zone in venue.zones:
        if any(abs(a[0] - b[0]) > EPS and abs(a[1] - b[1]) > EPS for a, b in _edges(zone.polygon)):
            issues.append(GraphIssue("non_rectilinear_room", "warning",
                                     f"{zone.name} has a slanted wall; its doors cannot be cut into it.", (zone.id,)))
        if _polygon_area(zone.polygon) < 1.0:
            issues.append(GraphIssue("room_too_small", "error", f"{zone.name} is smaller than 1 m².", (zone.id,)))
        if zone.initial_occupants > zone.max_capacity:
            issues.append(GraphIssue("over_capacity", "error",
                                     f"{zone.name} holds {zone.initial_occupants} people but its capacity is "
                                     f"{zone.max_capacity}.", (zone.id,)))

    # Rooms lie inside the declared extent (the 3D scene frames the extent, the overlap grid covers it).
    width, height = venue.extent
    for zone in venue.zones:
        if any(x < -EPS or y < -EPS or x > width + EPS or y > height + EPS for x, y in zone.polygon):
            issues.append(GraphIssue("room_outside_extent", "error",
                                     f"{zone.name} extends outside the {width:g} x {height:g} m building.", (zone.id,)))

    # Openings sit on walls: a door inside the wall both rooms share, an exit inside an outside wall of its room.
    # The whole opening must fit, not just its centre: a door at a corner or T-junction has no wall to open.
    for door in venue.doors:
        a, b = (zones[z] for z in door.zones)
        if not (_on_boundary(door.position, a.polygon) and _on_boundary(door.position, b.polygon)):
            issues.append(GraphIssue("door_off_shared_wall", "error",
                                     f"{door.id} is not on a wall shared by {a.name} and {b.name}.", (door.id,)))
        elif not _opening_fits(door.position, door.width, [a.polygon], [b.polygon]):
            issues.append(GraphIssue("door_wider_than_shared_wall", "error",
                                     f"{door.id} ({door.width:.1f} m) does not fit in the wall {a.name} and {b.name} "
                                     "share.", (door.id,)))
        if not MIN_OPENING_M <= door.width <= MAX_OPENING_M:
            issues.append(GraphIssue("unusual_width", "warning", f"{door.id} is {door.width:.1f} m wide.", (door.id,)))
    for exit_ in venue.exits:
        zone = zones[exit_.zone]
        others = [other for other in venue.zones if other.id != zone.id]
        shared = [other.id for other in others if _on_boundary(exit_.position, other.polygon)]
        if not _on_boundary(exit_.position, zone.polygon) or shared:
            issues.append(GraphIssue("exit_not_on_outside_wall", "error",
                                     f"{exit_.id} is not on an outside wall of {zone.name}.", (exit_.id, *shared)))
        elif not _opening_fits(exit_.position, exit_.width, [zone.polygon], None,
                               blocked=[other.polygon for other in others]):
            issues.append(GraphIssue("exit_wider_than_outside_wall", "error",
                                     f"{exit_.id} ({exit_.width:.1f} m) does not fit in an outside wall of {zone.name}.",
                                     (exit_.id,)))
        if not MIN_OPENING_M <= exit_.width <= MAX_OPENING_M:
            issues.append(GraphIssue("unusual_width", "warning", f"{exit_.id} is {exit_.width:.1f} m wide.", (exit_.id,)))

    # Overlap, exact for rectilinear rooms: cells between every distinct wall coordinate are either fully inside a
    # room or fully outside it, so two rooms sharing a cell share floor (a thin room inside another is caught too).
    xs = sorted({round(x, 6) for z in venue.zones for x, _ in z.polygon})
    ys = sorted({round(y, 6) for z in venue.zones for _, y in z.polygon})
    overlaps: Dict[Tuple[str, str], float] = {}
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            inside = [z.id for z in venue.zones if _strictly_inside((x0 + x1) / 2, (y0 + y1) / 2, z.polygon)]
            for k, first in enumerate(inside):
                for second in inside[k + 1:]:
                    overlaps[(first, second)] = overlaps.get((first, second), 0.0) + (x1 - x0) * (y1 - y0)
    for (first, second), area in sorted(overlaps.items()):
        if area > 1e-3:
            issues.append(GraphIssue("rooms_overlap", "error",
                                     f"{zones[first].name} and {zones[second].name} overlap by {area:.2f} m².",
                                     (first, second)))

    # Every room must reach an exit through a door people can use: open by default, or one the planner may open.
    if not venue.exits:
        issues.append(GraphIssue("no_exits", "error", "The building has no exit."))
    neighbours: Dict[str, List[str]] = {z.id: [] for z in venue.zones}
    for door in venue.doors:
        if door.default_state != "open" and not door.planner_can_open:
            continue
        a, b = door.zones
        neighbours[a].append(b)
        neighbours[b].append(a)
    reach = {x.zone for x in venue.exits}
    queue = deque(reach)
    while queue:
        for nxt in neighbours[queue.popleft()]:
            if nxt not in reach:
                reach.add(nxt)
                queue.append(nxt)
    for zone in venue.zones:
        if zone.id not in reach:
            issues.append(GraphIssue("room_unreachable", "error", f"No door path leads from {zone.name} to an exit.",
                                     (zone.id,)))

    # Planner limits: every state of the free doors is solved, and horizons above 120 s are refused.
    free = [d.id for d in venue.doors if d.planner_can_open and d.default_state == "closed"]
    if len(free) > MAX_FREE_DOORS:
        issues.append(GraphIssue("too_many_controllable_doors", "error",
                                 f"{len(free)} controllable doors; mark at most {MAX_FREE_DOORS}.", tuple(free)))
    if venue.default_horizon_seconds > MAX_PLANNER_HORIZON:
        issues.append(GraphIssue("horizon_too_long", "error",
                                 f"The horizon is {venue.default_horizon_seconds} s; the planner allows {MAX_PLANNER_HORIZON} s."))
    if sum(z.initial_occupants for z in venue.zones) == 0:
        issues.append(GraphIssue("no_occupants", "warning", "No modeled occupants; set a headcount."))
    if venue.led_map and max(end for _, end in venue.led_map.values()) >= MAX_PIXELS:
        issues.append(GraphIssue("light_strip_too_long", "error",
                                 f"The light map needs more than {MAX_PIXELS} on-screen pixels."))
    return issues


def _axis_spans(point, polygon) -> List[Tuple[str, float, float, float]]:
    """Axis-aligned edges of the polygon through the point as (axis, line, lo, hi); axis is the varying coordinate."""
    spans = []
    for (ax, ay), (bx, by) in _edges(polygon):
        if abs(ay - by) < EPS and abs(point[1] - ay) < EPS and min(ax, bx) - EPS <= point[0] <= max(ax, bx) + EPS:
            spans.append(("x", ay, min(ax, bx), max(ax, bx)))
        elif abs(ax - bx) < EPS and abs(point[0] - ax) < EPS and min(ay, by) - EPS <= point[1] <= max(ay, by) + EPS:
            spans.append(("y", ax, min(ay, by), max(ay, by)))
    return spans


def _opening_fits(point, width: float, sides: List, other_side: Optional[List], blocked: Optional[List] = None) -> bool:
    """True when [centre - width/2, centre + width/2] lies on one wall line, inside an edge of every polygon in
    ``sides`` (and of ``other_side`` for a door), and touches no edge of a ``blocked`` polygon (for an exit)."""
    for axis, line, lo, hi in _axis_spans(point, sides[0]):
        along = point[0] if axis == "x" else point[1]
        g0, g1 = along - width / 2, along + width / 2
        lo_all, hi_all = lo, hi
        for polygon in sides[1:] + (other_side or []):
            matching = [(l, h) for a, ln, l, h in _axis_spans(point, polygon) if a == axis and abs(ln - line) < EPS]
            if not matching:
                lo_all = hi_all = 0.0
                break
            lo_all, hi_all = max(lo_all, max(l for l, _ in matching)), min(hi_all, min(h for _, h in matching))
        if not (lo_all - EPS <= g0 and g1 <= hi_all + EPS):
            continue
        clash = False
        for polygon in blocked or []:
            for (ax, ay), (bx, by) in _edges(polygon):
                if axis == "x" and abs(ay - by) < EPS and abs(ay - line) < EPS:
                    clash |= min(ax, bx) < g1 - EPS and max(ax, bx) > g0 + EPS
                elif axis == "y" and abs(ax - bx) < EPS and abs(ax - line) < EPS:
                    clash |= min(ay, by) < g1 - EPS and max(ay, by) > g0 + EPS
        if not clash:
            return True
    return False


def errors_in(issues: List[GraphIssue]) -> List[GraphIssue]:
    return [issue for issue in issues if issue.severity == "error"]


def summary(issues: List[GraphIssue]) -> Dict[str, int]:
    return {"errors": len(errors_in(issues)), "warnings": sum(1 for i in issues if i.severity == "warning")}


def first_error(issues: List[GraphIssue]) -> Optional[GraphIssue]:
    found = errors_in(issues)
    return found[0] if found else None
