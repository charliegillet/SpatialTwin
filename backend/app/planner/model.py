"""
Fixed Reviewed Venue Graph Specification
"""

from typing import Dict, List, Set
from pydantic import BaseModel, Field


class ZoneSpec(BaseModel):
    id: str
    name: str
    max_capacity: int
    initial_occupants: int = 0


class PortalSpec(BaseModel):
    id: str
    role: str
    from_zone: str
    to_zone: str
    width_meters: float
    throughput_per_sec: float
    travel_time_seconds: int
    default_state: str = "open"  # "open" or "closed"
    can_be_blocked: bool = True
    is_actuated: bool = False


class BoundarySpec(BaseModel):
    id: str
    from_zone: str
    service_rate_per_sec: float
    can_be_blocked: bool = True


class VenueGraph(BaseModel):
    geometry_revision: str = "geom-shack15-v1"
    zones: Dict[str, ZoneSpec]
    portals: Dict[str, PortalSpec]
    boundaries: Dict[str, BoundarySpec]
    default_horizon_seconds: int = 60
    time_step_seconds: int = 2


def get_default_venue_graph() -> VenueGraph:
    return VenueGraph(
        geometry_revision="geom-shack15-v1",
        zones={
            "EVENT": ZoneSpec(id="EVENT", name="Main Event Hall", max_capacity=200, initial_occupants=120),
            "WEST": ZoneSpec(id="WEST", name="West Corridor", max_capacity=60, initial_occupants=0),
            "EAST": ZoneSpec(id="EAST", name="East Corridor", max_capacity=60, initial_occupants=0),
            "RESERVE": ZoneSpec(id="RESERVE", name="Reserve Channel", max_capacity=40, initial_occupants=0),
        },
        portals={
            "P1": PortalSpec(
                id="P1", role="main_west", from_zone="EVENT", to_zone="WEST",
                width_meters=2.4, throughput_per_sec=3.0, travel_time_seconds=2,
                default_state="open", can_be_blocked=True
            ),
            "P2": PortalSpec(
                id="P2", role="main_east", from_zone="EVENT", to_zone="EAST",
                width_meters=2.4, throughput_per_sec=3.0, travel_time_seconds=2,
                default_state="open", can_be_blocked=True
            ),
            "P3": PortalSpec(
                id="P3", role="miniature_reserve_gate", from_zone="EVENT", to_zone="RESERVE",
                width_meters=1.8, throughput_per_sec=2.5, travel_time_seconds=2,
                default_state="closed", can_be_blocked=False, is_actuated=True
            ),
            "P4": PortalSpec(
                id="P4", role="fixed_reserve_to_east", from_zone="RESERVE", to_zone="EAST",
                width_meters=2.0, throughput_per_sec=3.0, travel_time_seconds=2,
                default_state="open", can_be_blocked=False
            ),
        },
        boundaries={
            "B1": BoundarySpec(id="B1", from_zone="WEST", service_rate_per_sec=1.5, can_be_blocked=False),
            "B2": BoundarySpec(id="B2", from_zone="EAST", service_rate_per_sec=1.5, can_be_blocked=True),
        },
        default_horizon_seconds=40,
        time_step_seconds=2,
    )
