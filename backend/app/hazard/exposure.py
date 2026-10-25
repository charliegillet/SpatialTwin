"""Modeled exposure over a checked timeline."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

EXPOSURE_LABEL = "modeled, not a casualty or survival prediction"


def modeled_exposure_people_seconds(
    timeline: List[Dict[str, Any]], hazard_zone_ids: Iterable[str], dt: int, population: int,
    zone_ids: Iterable[str] = ("EVENT", "WEST", "EAST", "RESERVE"),
) -> Tuple[int, str]:
    """Sum of occupancy in the declared hazard zones times dt over all timeline frames.

    Returns ``(people_seconds, label)``. The result is modeled, not a casualty or
    survival prediction. Every frame must conserve the population (all zone
    occupancy + in-transit + completed == population) or ValueError is raised.
    """
    hazard = {z.lower() for z in hazard_zone_ids}
    zones = [z.lower() for z in zone_ids]
    total = 0
    for frame in timeline:
        in_zones = sum(frame[f"{z}_occupancy"] for z in zones)
        if in_zones + frame["in_transit_occupancy"] + frame["total_completed"] != population:
            raise ValueError("timeline_conservation_violated")
        total += sum(frame[f"{z}_occupancy"] for z in hazard) * dt
    return total, EXPOSURE_LABEL
