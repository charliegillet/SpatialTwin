"""Deterministic checks on a venue graph before an operator may accept it.

Gemini proposes the rooms, doors and exits; these checks decide whether the result can be planned and drawn.
Every issue is typed so the UI, the critique loop and the tests read the same codes. Errors block Accept;
warnings are shown next to the evidence.
"""
from __future__ import annotations

import math
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
OVERLAP_CELL_M = 0.25


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

    # Openings sit on walls: a door on the wall both rooms share, an exit on an outside wall of its room.
    for door in venue.doors:
        a, b = (zones[z] for z in door.zones)
        if not (_on_boundary(door.position, a.polygon) and _on_boundary(door.position, b.polygon)):
            issues.append(GraphIssue("door_off_shared_wall", "error",
                                     f"{door.id} is not on a wall shared by {a.name} and {b.name}.", (door.id,)))
        if not MIN_OPENING_M <= door.width <= MAX_OPENING_M:
            issues.append(GraphIssue("unusual_width", "warning", f"{door.id} is {door.width:.1f} m wide.", (door.id,)))
    for exit_ in venue.exits:
        zone = zones[exit_.zone]
        shared = [other.id for other in venue.zones
                  if other.id != zone.id and _on_boundary(exit_.position, other.polygon)]
        if not _on_boundary(exit_.position, zone.polygon) or shared:
            issues.append(GraphIssue("exit_not_on_outside_wall", "error",
                                     f"{exit_.id} is not on an outside wall of {zone.name}.", (exit_.id, *shared)))
        if not MIN_OPENING_M <= exit_.width <= MAX_OPENING_M:
            issues.append(GraphIssue("unusual_width", "warning", f"{exit_.id} is {exit_.width:.1f} m wide.", (exit_.id,)))

    # Overlap, sampled on a grid: two rooms may share walls but not floor.
    width, height = venue.extent
    columns, rows = max(1, math.ceil(width / OVERLAP_CELL_M)), max(1, math.ceil(height / OVERLAP_CELL_M))
    overlaps: Dict[Tuple[str, str], int] = {}
    for i in range(columns):
        for j in range(rows):
            x, y = (i + 0.5) * width / columns, (j + 0.5) * height / rows
            inside = [z.id for z in venue.zones if _strictly_inside(x, y, z.polygon)]
            for k, first in enumerate(inside):
                for second in inside[k + 1:]:
                    overlaps[(first, second)] = overlaps.get((first, second), 0) + 1
    for (first, second), cells in sorted(overlaps.items()):
        area = cells * (width / columns) * (height / rows)
        if area >= 0.5:
            issues.append(GraphIssue("rooms_overlap", "error",
                                     f"{zones[first].name} and {zones[second].name} overlap by about {area:.1f} m².",
                                     (first, second)))

    # Every room must reach an exit through some door (the planner may open closed doors).
    if not venue.exits:
        issues.append(GraphIssue("no_exits", "error", "The building has no exit."))
    neighbours: Dict[str, List[str]] = {z.id: [] for z in venue.zones}
    for door in venue.doors:
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
    return issues


def errors_in(issues: List[GraphIssue]) -> List[GraphIssue]:
    return [issue for issue in issues if issue.severity == "error"]


def summary(issues: List[GraphIssue]) -> Dict[str, int]:
    return {"errors": len(errors_in(issues)), "warnings": sum(1 for i in issues if i.severity == "warning")}


def first_error(issues: List[GraphIssue]) -> Optional[GraphIssue]:
    found = errors_in(issues)
    return found[0] if found else None
