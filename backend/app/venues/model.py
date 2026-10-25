"""Venue model (schema 2.0.0): pydantic model, validator and zone hit test.

building-v2 is the built-in venue; its JSON file under venue/ is the source of truth. Other venues are compiled
from a Gemini reading and accepted by an operator (backend/app/venues/registry.py). The shape mirrors
frontend/src/twin/types.ts (VenueV2) field for field.
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

HazardKind = Literal["FIRE", "SMOKE", "GAS", "CHEMICAL", "WATER"]
DoorActuation = Literal["hold_open", "simulated_servo", "motorized", "indicator_only", "fixed"]
DoorKind = Literal["fire_door", "smoke_door", "room_door", "servo_door", "roller_door", "opening"]

_ID = re.compile(r"^[A-Z0-9_]+$")
VENUE_ID_PATTERN = r"^[a-z0-9-]{3,40}$"
BUILTIN_VENUE_ID = "building-v2"
VENUE_FILE = Path(__file__).resolve().parents[3] / "venue" / "building_v2.json"

Point2 = Tuple[float, float]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VenueZone(_Strict):
    id: str
    name: str
    max_capacity: int = Field(ge=0)
    initial_occupants: int = Field(ge=0)
    polygon: List[Point2]


class VenueDoor(_Strict):
    id: str
    zones: Tuple[str, str]
    position: Point2
    width: float = Field(gt=0)
    throughput_per_sec: float = Field(gt=0)
    travel_time_seconds: float = Field(ge=0)
    default_state: Literal["open", "closed"]
    kind: DoorKind
    actuation: DoorActuation
    planner_can_open: bool
    note: Optional[str] = None


class VenueExit(_Strict):
    id: str
    zone: str
    name: str
    position: Point2
    width: float = Field(gt=0)
    service_rate_per_sec: float = Field(gt=0)
    # "stair": an interior exit stair (the way down inside the floor plate), strictly inside its own zone and on no
    # wall. Unset (building-v2) and "door"/"window" exits must sit on an outside wall.
    kind: Optional[Literal["door", "stair", "window"]] = None


class HazardDefaults(_Strict):
    untenable_s: Optional[int] = None
    throughput_multiplier: Optional[float] = None
    travel_multiplier: Optional[float] = None


FloorMaterial = Literal["wood", "tile", "carpet", "stone", "concrete", "terrazzo", "unknown"]
HexColor = str  # "#rrggbb" or ""; checked by the pattern below
_HEX_FIELD = dict(pattern=r"^(#[0-9a-f]{6})?$")


class ZoneLook(_Strict):
    """How a room looks (from a video walkthrough). Presentation only: no solver, checker or graph check reads it."""
    wall_color: HexColor = Field(default="", **_HEX_FIELD)
    floor_color: HexColor = Field(default="", **_HEX_FIELD)
    floor_material: FloorMaterial = "unknown"


class VenueFurniture(_Strict):
    """A piece of furniture drawn in the twin. Presentation only: it never blocks, slows or re-routes anyone."""
    id: str = Field(pattern=r"^F[0-9]{1,3}$")
    zone: str
    label: str = Field(min_length=1, max_length=40)
    category: str = Field(default="furniture", max_length=24)
    position: Point2
    width: float = Field(gt=0, le=10)
    depth: float = Field(gt=0, le=10)
    height: float = Field(gt=0, le=4)
    yaw_deg: float = Field(default=0, ge=-180, le=180)
    color: HexColor = Field(default="", **_HEX_FIELD)


class VenueFeature(_Strict):
    """A railing, glass partition or window from a room reading, drawn on a wall line. Looks only."""
    kind: Literal["railing", "glass", "window"]
    a: Point2
    b: Point2
    height: float = Field(gt=0, le=6)
    sill: float = Field(default=0, ge=0, le=4)


class VenueAppearance(_Strict):
    zones: Dict[str, ZoneLook] = Field(default_factory=dict)
    furniture: List[VenueFurniture] = Field(default_factory=list, max_length=60)
    features: List[VenueFeature] = Field(default_factory=list, max_length=100)


class VenueV2(_Strict):
    schema_version: Literal["2.0.0"]
    venue_id: str = Field(pattern=VENUE_ID_PATTERN)
    geometry_revision: str
    provenance: str
    units: Literal["m"]
    extent: Point2
    default_horizon_seconds: int = Field(gt=0)
    time_step_seconds: int = Field(gt=0)
    zones: List[VenueZone]
    doors: List[VenueDoor]
    exits: List[VenueExit]
    led_map: Dict[str, Tuple[int, int]]
    hazard_defaults: Dict[HazardKind, HazardDefaults]
    appearance: Optional[VenueAppearance] = None

    @model_validator(mode="after")
    def _validate(self) -> "VenueV2":
        def unique(kind: str, ids: List[str]) -> set:
            for value in ids:
                if not _ID.match(value):
                    raise ValueError(f"{kind} id {value!r} must match [A-Z0-9_]+")
            if len(set(ids)) != len(ids):
                raise ValueError(f"duplicate {kind} ids")
            return set(ids)

        zone_ids = unique("zone", [z.id for z in self.zones])
        door_ids = unique("door", [d.id for d in self.doors])
        exit_ids = unique("exit", [e.id for e in self.exits])
        if zone_ids & door_ids or zone_ids & exit_ids or door_ids & exit_ids:
            raise ValueError("zone, door and exit ids must not collide")
        for zone in self.zones:
            if len(zone.polygon) < 3:
                raise ValueError(f"zone {zone.id} polygon needs at least 3 points")
        seen_pairs = set()
        for door in self.doors:
            a, b = door.zones
            if a not in zone_ids or b not in zone_ids:
                raise ValueError(f"door {door.id} references an unknown zone")
            if a == b:
                raise ValueError(f"door {door.id} joins a zone to itself")
            pair = frozenset((a, b))
            if pair in seen_pairs:
                raise ValueError(f"more than one door joins {a} and {b}")
            seen_pairs.add(pair)
        for ex in self.exits:
            if ex.zone not in zone_ids:
                raise ValueError(f"exit {ex.id} references an unknown zone")
        for element in self.led_map:
            if element not in door_ids and element not in exit_ids:
                raise ValueError(f"led_map references unknown element {element}")
        for start, end in self.led_map.values():
            if start < 0 or end < start:
                raise ValueError("led_map ranges must be non-negative and ordered")
        if self.default_horizon_seconds % self.time_step_seconds:
            raise ValueError("default horizon must be a multiple of the time step")
        if self.appearance is not None:
            for zone_id in self.appearance.zones:
                if zone_id not in zone_ids:
                    raise ValueError(f"appearance references unknown zone {zone_id}")
            unique("furniture", [f.id for f in self.appearance.furniture])
            for piece in self.appearance.furniture:
                if piece.zone not in zone_ids:
                    raise ValueError(f"furniture {piece.id} references an unknown zone")
        return self

    def planning_json(self) -> dict:
        """The venue without its looks: what a solver, checker or sandbox needs."""
        return {key: value for key, value in self.to_json().items() if key != "appearance"}

    def zone(self, zone_id: str) -> VenueZone:
        return next(z for z in self.zones if z.id == zone_id)

    def door_between(self, a: str, b: str) -> Optional[VenueDoor]:
        pair = {a, b}
        return next((d for d in self.doors if set(d.zones) == pair), None)

    def locate_zone(self, x: float, y: float) -> Optional[str]:
        """Zone containing the point; a point on a shared wall resolves to the first zone in venue order."""
        for zone in self.zones:
            if point_in_polygon(x, y, zone.polygon):
                return zone.id
        return None

    def to_json(self) -> dict:
        return self.model_dump(mode="json", exclude_none=True)


def _distance_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    t = 0.0 if length_sq == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def point_in_polygon(x: float, y: float, polygon: List[Point2]) -> bool:
    """Even-odd ray cast; a point exactly on an edge counts as inside (same rule as frontend geometry.ts)."""
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if _distance_to_segment(x, y, xi, yi, xj, yj) < 1e-9:
            return True
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


@lru_cache(maxsize=1)
def load_building_v2() -> VenueV2:
    return VenueV2.model_validate(json.loads(VENUE_FILE.read_text()))


def get_venue(venue_id: str) -> Optional[VenueV2]:
    """The built-in venue, or an accepted venue from the registry. Drafts are never returned."""
    if venue_id == BUILTIN_VENUE_ID:
        return load_building_v2()
    if not isinstance(venue_id, str) or not re.match(VENUE_ID_PATTERN, venue_id):
        return None
    from backend.app.venues.registry import venue_registry  # registry imports this module
    return venue_registry().accepted_venue(venue_id)
