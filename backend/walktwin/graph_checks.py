"""Deterministic validation of an extracted venue graph (plain axis-aligned geometry)."""
from __future__ import annotations

from collections import Counter, deque
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .contracts import Door, Scenario, VenueGraph, Zone

OUTSIDE = "OUTSIDE"
DOOR_TOLERANCE_M = 0.5
OVERLAP_MAX_M2 = 0.25


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    severity: Literal["error", "warning"]
    element_id: str | None
    message: str


def has_errors(findings: list[Finding]) -> bool:
    return any(f.severity == "error" for f in findings)


def _err(code: str, element_id: str | None, message: str) -> Finding:
    return Finding(code=code, severity="error", element_id=element_id, message=message)


def _warn(code: str, element_id: str | None, message: str) -> Finding:
    return Finding(code=code, severity="warning", element_id=element_id, message=message)


# --- geometry ---------------------------------------------------------------

Rect = tuple[float, float, float, float]


def _bounds(r: Rect) -> tuple[float, float, float, float]:
    return r[0], r[1], r[0] + r[2], r[1] + r[3]


def _overlap_area(a: Rect, b: Rect) -> float:
    ax0, ay0, ax1, ay1 = _bounds(a)
    bx0, by0, bx1, by1 = _bounds(b)
    w = min(ax1, bx1) - max(ax0, bx0)
    h = min(ay1, by1) - max(ay0, by0)
    return w * h if w > 0 and h > 0 else 0.0


def _dist_to_shared_edge(p: tuple[float, float], a: Rect, b: Rect) -> float | None:
    """Distance from p to the region where the edges of a and b coincide/overlap.

    Rects that touch share a segment (their closed intersection). Gaps of up to
    the door tolerance are forgiven by growing each rect by half of it.
    Returns None when the rects do not share any boundary.
    """
    g = DOOR_TOLERANCE_M / 2
    ax0, ay0, ax1, ay1 = _bounds(a)
    bx0, by0, bx1, by1 = _bounds(b)
    x0, x1 = max(ax0, bx0), min(ax1, bx1)
    y0, y1 = max(ay0, by0), min(ay1, by1)
    # grow the intersection window by the gap allowance instead of the rects
    if x1 < x0 - 2 * g or y1 < y0 - 2 * g:
        return None
    if x1 < x0:
        x0 = x1 = (x0 + x1) / 2
    if y1 < y0:
        y0 = y1 = (y0 + y1) / 2
    dx = max(x0 - p[0], 0.0, p[0] - x1)
    dy = max(y0 - p[1], 0.0, p[1] - y1)
    return (dx * dx + dy * dy) ** 0.5


def _dist_to_perimeter(p: tuple[float, float], r: Rect) -> float:
    x0, y0, x1, y1 = _bounds(r)
    dx = max(x0 - p[0], 0.0, p[0] - x1)
    dy = max(y0 - p[1], 0.0, p[1] - y1)
    if dx > 0 or dy > 0:
        return (dx * dx + dy * dy) ** 0.5
    return min(p[0] - x0, x1 - p[0], p[1] - y0, y1 - p[1])


# --- reachability -------------------------------------------------------------


def _effectively_open(door: Door, scenario: Scenario | None) -> bool:
    opened = door.state == "open"
    if scenario is not None:
        if f"OPEN:{door.id}" in scenario.interventions:
            opened = True
        if any(h.door_id == door.id for h in scenario.hazards):
            return False  # reachability is static: any hazard closes the door
    return opened


def reachable_zones(graph: VenueGraph, scenario: Scenario | None = None) -> set[str]:
    """Zones reachable from OUTSIDE through effectively open doors."""
    adj: dict[str, set[str]] = {}
    for d in graph.doors:
        if _effectively_open(d, scenario):
            adj.setdefault(d.a, set()).add(d.b)
            adj.setdefault(d.b, set()).add(d.a)
    seen = {OUTSIDE}
    queue = deque([OUTSIDE])
    while queue:
        for nxt in adj.get(queue.popleft(), ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    zone_ids = {z.id for z in graph.zones}
    return seen & zone_ids


# --- checks -------------------------------------------------------------------


def check_graph(graph: VenueGraph, video_duration_s: float) -> list[Finding]:
    findings: list[Finding] = []
    zones: dict[str, Zone] = {}
    for z in graph.zones:
        zones.setdefault(z.id, z)

    # duplicate ids (zones and doors share one namespace check per kind)
    for kind, ids in (("zone", [z.id for z in graph.zones]), ("door", [d.id for d in graph.doors])):
        for ident, n in Counter(ids).items():
            if n > 1:
                findings.append(_err("DUPLICATE_ID", ident, f"{kind} id {ident} appears {n} times"))

    # door references and boundary placement
    for d in graph.doors:
        bad = [
            ref
            for ref in (d.a, d.b)
            if ref != OUTSIDE and ref not in zones
        ]
        if d.a == OUTSIDE:
            bad.append(d.a)
        for ref in bad:
            findings.append(_err("UNKNOWN_ZONE_REF", d.id, f"door {d.id} references unknown zone {ref}"))
        if bad:
            continue
        za = zones[d.a]
        if d.b == OUTSIDE:
            dist = _dist_to_perimeter(d.position, za.rect)
            where = f"edge of {d.a}"
        else:
            dist = _dist_to_shared_edge(d.position, za.rect, zones[d.b].rect)
            where = f"shared edge of {d.a} and {d.b}"
        if dist is None or dist > DOOR_TOLERANCE_M:
            gap = "no shared edge" if dist is None else f"{dist:.2f} m"
            findings.append(
                _err("DOOR_OFF_BOUNDARY", d.id, f"door {d.id} is off the {where} ({gap})")
            )

    # zone overlap
    zl = list(graph.zones)
    for i in range(len(zl)):
        for j in range(i + 1, len(zl)):
            area = _overlap_area(zl[i].rect, zl[j].rect)
            if area > OVERLAP_MAX_M2:
                findings.append(
                    _err(
                        "ZONE_OVERLAP",
                        zl[i].id,
                        f"zones {zl[i].id} and {zl[j].id} overlap by {area:.2f} m2",
                    )
                )

    # exits
    if not any(d.b == OUTSIDE for d in graph.doors):
        findings.append(_err("NO_EXIT", None, "no door leads to OUTSIDE"))

    # evidence range
    for el in (*graph.zones, *graph.doors):
        for ev in el.evidence:
            if ev.end_s > video_duration_s:
                findings.append(
                    _err(
                        "EVIDENCE_OUT_OF_RANGE",
                        el.id,
                        f"{el.id} evidence ends at {ev.end_s}s, video is {video_duration_s}s",
                    )
                )

    # keyframes
    for k in graph.keyframes:
        if k.zone_id not in zones:
            findings.append(
                _err("KEYFRAME_UNKNOWN_ZONE", k.zone_id, f"keyframe at {k.t_s}s names unknown zone {k.zone_id}")
            )

    # warnings
    for d in graph.doors:
        if d.state == "unknown":
            findings.append(_warn("UNKNOWN_DOOR_STATE", d.id, f"door {d.id} state is unknown (treated as closed)"))
    reach = reachable_zones(graph)
    for z in graph.zones:
        if z.id not in reach:
            findings.append(_warn("UNREACHABLE_ZONE", z.id, f"zone {z.id} cannot be reached from OUTSIDE through open doors"))

    return findings
