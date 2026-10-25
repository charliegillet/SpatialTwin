"""What a phone exit sign shows, derived from the server-side incident mirror (backend/app/incident).

The sign follows the incident's latest *checked* plan, exactly like the 3D twin's exit lamps (incident.md, recipe
step 5): ``green_flash`` safe with modeled flow, ``green`` safe without flow, ``red_x`` unsafe, ``red_static`` gas lock.
Anything without a checker-valid plan is never shown as a lamp:

- ``inactive``: the incident is on another venue (this sign belongs to a building that is not on screen);
- ``normal``: no hazards; lamps from the no-hazard plan, or none yet (the page shows a steady exit sign);
- ``incident``: hazards and a valid plan; lamps from that plan;
- ``unchecked``: hazards but the plan was withdrawn (re-plan failed) or is not valid; no lamps.

Hazards are reduced to type + room name. Nothing else from the plan (door states, reasons, hashes, coordinates)
leaves this module.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from backend.app.incident.events import now_iso
from backend.app.incident.manager import IncidentManager
from backend.app.signs.models import SignExit, SignHazard, SignState
from backend.app.venues.model import BUILTIN_VENUE_ID, VenueV2, _distance_to_segment, point_in_polygon

WALL_EPSILON_M = 1e-6
HAZARD_TYPES = {"FIRE", "SMOKE", "GAS", "CHEMICAL", "WATER"}


def venue_name(venue: VenueV2) -> str:
    if venue.venue_id == BUILTIN_VENUE_ID:
        return "Building v2"
    try:
        from backend.app.venues.registry import venue_registry
        record = venue_registry().venue_record(venue.venue_id) or {}
    except Exception:  # noqa: BLE001 - a display name must never fail a sign
        record = {}
    name = record.get("name")
    return name.strip()[:80] if isinstance(name, str) and name.strip() else venue.venue_id


def _room_of(venue: VenueV2, hazard: Dict[str, Any]) -> Optional[str]:
    zone_id = hazard.get("zone_id")
    if not zone_id:
        position = hazard.get("position") or {}
        try:
            zone_id = venue.locate_zone(float(position.get("x")), float(position.get("y")))
        except (TypeError, ValueError):
            zone_id = None
    zone = next((z for z in venue.zones if z.id == zone_id), None)
    return zone.name if zone else None


def sign_state(manager: IncidentManager, venue: VenueV2, exit_id: Optional[str] = None,
               expires_at: Optional[str] = None) -> SignState:
    """The public sign view of ``venue`` (one exit when ``exit_id`` is given). Raises KeyError for an unknown exit."""
    exits = venue.exits if exit_id is None else [x for x in venue.exits if x.id == exit_id]
    if exit_id is not None and not exits:
        raise KeyError(exit_id)
    incident = manager.state()
    base = {"venue_id": venue.venue_id, "venue_name": venue_name(venue), "expires_at": expires_at,
            "server_time": now_iso()}
    dark = [SignExit(exit_id=x.id, name=x.name, lamp=None, routed=None) for x in exits]
    if (incident.venue_id, incident.geometry_revision) != (venue.venue_id, venue.geometry_revision):
        return SignState(status="inactive", plan_revision=None, exits=dark, hazards=[], **base)
    hazards: List[SignHazard] = []
    for hazard in incident.hazards:
        room = _room_of(venue, hazard)
        if room is not None and hazard.get("type") in HAZARD_TYPES:
            hazards.append(SignHazard(type=hazard["type"], room=room))
    plan = incident.plan
    if plan is None and not incident.hazards and incident.plan_error is None:
        return SignState(status="normal", plan_revision=incident.plan_revision, exits=dark, hazards=[], **base)
    if plan is None or not plan.valid:
        return SignState(status="unchecked", plan_revision=incident.plan_revision, exits=dark, hazards=hazards, **base)
    by_id = {x.id: x for x in plan.exits}
    lit = [SignExit(exit_id=x.id, name=x.name, lamp=by_id[x.id].lamp if x.id in by_id else None,
                    routed=by_id[x.id].modeled_crossings if x.id in by_id else None) for x in exits]
    return SignState(status="incident" if incident.hazards else "normal", plan_revision=plan.plan_revision,
                     plan_label=plan.label, exits=lit, hazards=hazards, **base)


def zone_at(venue: VenueV2, x: float, y: float) -> Optional[str]:
    """The zone whose polygon holds the point *strictly* inside (not on any wall), else None.

    ``VenueV2.locate_zone`` counts a wall as inside and resolves a shared wall to the first zone; a judge's tap that
    lands exactly on a wall is ambiguous, so it is refused as outside rather than guessed.
    """
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    for zone in venue.zones:
        if not point_in_polygon(x, y, zone.polygon):
            continue
        edges = zip(zone.polygon, zone.polygon[1:] + zone.polygon[:1])
        if all(_distance_to_segment(x, y, ax, ay, bx, by) > WALL_EPSILON_M for (ax, ay), (bx, by) in edges):
            return zone.id
    return None


def plan_geometry(venue: VenueV2) -> Dict[str, Any]:
    """Venue geometry for the phone's map: rooms, doors, exits. No door states, plan, occupants, reasons or hashes."""
    return {
        "extent": [venue.extent[0], venue.extent[1]],
        "rooms": [{"id": z.id, "name": z.name, "polygon": [[p[0], p[1]] for p in z.polygon]} for z in venue.zones],
        "doors": [{"id": d.id, "position": [d.position[0], d.position[1]], "width": d.width} for d in venue.doors],
        "exits": [{"id": x.id, "name": x.name, "position": [x.position[0], x.position[1]], "kind": x.kind or "door"}
                  for x in venue.exits],
    }


def interior_point(venue: VenueV2, zone_id: str) -> Optional[Tuple[float, float]]:
    """A point strictly inside the zone that the venue's own hit test resolves to that zone.

    The area centroid is tried first (it is what the twin's keyboard route uses); an L-shaped room whose centroid
    falls outside, or onto a wall, falls back to the middle of the widest span of a few horizontal scanlines.
    """
    zone = next((z for z in venue.zones if z.id == zone_id), None)
    if zone is None:
        return None
    polygon = zone.polygon
    candidates: List[Tuple[float, float]] = []
    area = cx = cy = 0.0
    for i in range(len(polygon)):
        x0, y0 = polygon[i]
        x1, y1 = polygon[(i + 1) % len(polygon)]
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(area) > 1e-9:
        candidates.append((cx / (3 * area), cy / (3 * area)))
    ys = [p[1] for p in polygon]
    for fraction in (0.5, 0.3, 0.7, 0.15, 0.85):
        y = min(ys) + (max(ys) - min(ys)) * fraction
        crossings = sorted(x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                           for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1])
                           if (y0 > y) != (y1 > y))
        spans = [(crossings[i], crossings[i + 1]) for i in range(0, len(crossings) - 1, 2)]
        if spans:
            left, right = max(spans, key=lambda span: span[1] - span[0])
            candidates.append(((left + right) / 2, y))
    for x, y in candidates:
        point = (round(x, 3), round(y, 3))
        nudged = [(point[0] + dx, point[1] + dy) for dx in (-0.01, 0.01) for dy in (-0.01, 0.01)]
        if (venue.locate_zone(*point) == zone_id and point_in_polygon(*point, polygon)
                and all(point_in_polygon(px, py, polygon) for px, py in nudged)):
            return point
    return None
