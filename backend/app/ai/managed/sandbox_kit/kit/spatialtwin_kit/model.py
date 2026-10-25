"""Standalone venue shim for the sandbox: the attributes the copied solver, checker and effects read.

The server's VenueV2 is a pydantic model; the sandbox has no pydantic guarantee, so this is a plain dataclass
loader for /workspace/inputs/venue.json. It does not validate the venue: the local checker on the laptop already
did, and anything computed here is re-verified there.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class VenueZone:
    id: str
    name: str
    max_capacity: int
    initial_occupants: int
    polygon: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class VenueDoor:
    id: str
    zones: Tuple[str, str]
    throughput_per_sec: float
    travel_time_seconds: float
    default_state: str
    kind: str
    actuation: str
    planner_can_open: bool
    position: Tuple[float, float] = (0.0, 0.0)
    width: float = 1.0


@dataclass
class VenueExit:
    id: str
    zone: str
    name: str
    service_rate_per_sec: float
    position: Tuple[float, float] = (0.0, 0.0)
    width: float = 1.0


@dataclass
class HazardDefaults:
    untenable_s: Optional[int] = None
    throughput_multiplier: Optional[float] = None
    travel_multiplier: Optional[float] = None


@dataclass
class VenueV2:
    venue_id: str
    geometry_revision: str
    provenance: str
    default_horizon_seconds: int
    time_step_seconds: int
    zones: List[VenueZone]
    doors: List[VenueDoor]
    exits: List[VenueExit]
    hazard_defaults: Dict[str, HazardDefaults]

    @classmethod
    def from_json(cls, data: dict) -> "VenueV2":
        return cls(
            venue_id=data["venue_id"], geometry_revision=data["geometry_revision"],
            provenance=data.get("provenance", ""), default_horizon_seconds=int(data["default_horizon_seconds"]),
            time_step_seconds=int(data["time_step_seconds"]),
            zones=[VenueZone(id=z["id"], name=z["name"], max_capacity=int(z["max_capacity"]),
                             initial_occupants=int(z["initial_occupants"]),
                             polygon=[tuple(p) for p in z.get("polygon", [])]) for z in data["zones"]],
            doors=[VenueDoor(id=d["id"], zones=(d["zones"][0], d["zones"][1]),
                             throughput_per_sec=float(d["throughput_per_sec"]),
                             travel_time_seconds=float(d["travel_time_seconds"]), default_state=d["default_state"],
                             kind=d["kind"], actuation=d["actuation"], planner_can_open=bool(d["planner_can_open"]),
                             position=tuple(d.get("position", (0.0, 0.0))), width=float(d.get("width", 1.0)))
                   for d in data["doors"]],
            exits=[VenueExit(id=e["id"], zone=e["zone"], name=e["name"],
                             service_rate_per_sec=float(e["service_rate_per_sec"]),
                             position=tuple(e.get("position", (0.0, 0.0))), width=float(e.get("width", 1.0)))
                   for e in data["exits"]],
            hazard_defaults={kind: HazardDefaults(**{k: v for k, v in (values or {}).items()
                                                     if k in ("untenable_s", "throughput_multiplier",
                                                              "travel_multiplier")})
                             for kind, values in data.get("hazard_defaults", {}).items()})
