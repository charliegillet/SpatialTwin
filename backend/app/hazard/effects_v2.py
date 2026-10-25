"""Typed hazards -> solver inputs and display effects for building-v2 (v1 hazard files are untouched).

Declared model assumptions (also returned verbatim in the response):
  * a hazard applies to the whole zone that contains its point;
  * same-zone precedence for the zone status: FIRE = CHEMICAL > GAS > SMOKE > WATER (FIRE shown over CHEMICAL);
    only the effective hazards drive the zone dynamics, while safety locks are unions across all hazards;
  * closing a door means closed to ENTRY; occupants inside may still leave until the zone is untenable;
  * several zones combine as min untenable time, min throughput factor, max travel factor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from backend.app.planner.checker_v2 import SolveInputs
from backend.app.venues.model import VenueDoor, VenueV2

PRECEDENCE = {"FIRE": 3, "CHEMICAL": 3, "GAS": 2, "SMOKE": 1, "WATER": 0}
DISPLAY_RANK = {"FIRE": 4, "CHEMICAL": 3, "GAS": 2, "SMOKE": 1, "WATER": 0}
HAZARDOUS = {"FIRE", "SMOKE", "GAS", "CHEMICAL"}
LOCKABLE = {"simulated_servo", "motorized"}

MODEL_ASSUMPTIONS = [
    "building-v2 model: illustrative eight-zone building, synthetic population and declared rates; not a surveyed plan.",
    "A hazard applies to the whole zone that contains its point.",
    "Same-zone precedence for zone status: FIRE = CHEMICAL > GAS > SMOKE > WATER; only the effective hazards "
    "drive the zone, safety locks (gas) are unions across all hazards.",
    "Closing a door means closed to entry; occupants inside a hazard zone may still leave until it is untenable.",
    "Several hazards combine as the minimum untenable time, the minimum throughput factor and the maximum travel factor.",
    "FIRE and CHEMICAL: no entry from the start; untenable at T; hold-open doors bounding the zone release; exits in the zone are unsafe.",
    "SMOKE: no entry, throughput x0.5 on bounding doors and zone exits, untenable at T, hold-open doors release, zone exits unsafe and closed from detection.",
    "GAS: no entry, untenable at T; the system opens and releases no door and switches nothing; motorized and servo doors "
    "bounding the zone stay locked in their default state; their lights are set static red once.",
    "WATER: passable; throughput x0.5 and travel x2 on bounding doors and zone exits; no door changes.",
    "Counts are modeled crossings inside this model with declared times, rates and a fixed horizon; never survival or casualty predictions.",
]


def venue_model_line(venue: VenueV2) -> str:
    """The first assumption names the venue; building-v2 keeps its published wording."""
    if venue.venue_id == "building-v2":
        return MODEL_ASSUMPTIONS[0]
    return f"{venue.venue_id} model: {venue.provenance}"


@dataclass
class ZoneEffect:
    zone_id: str
    status: str  # passable | slowed | no_entry
    hazard_type: Optional[str]
    untenable_at_s: Optional[int]
    throughput_multiplier: Optional[float]


@dataclass
class DoorEffect:
    entry_denied_into: Set[str] = field(default_factory=set)
    released: bool = False  # hold-open door released (closed) by a fire/smoke/chemical rule
    gas_held: bool = False  # lamp set static red, nothing switched
    gas_locked: bool = False  # servo/motorized door locked in default state
    reasons: List[str] = field(default_factory=list)


@dataclass
class ExitEffect:
    unsafe: bool = False
    gas: bool = False
    reasons: List[str] = field(default_factory=list)


@dataclass
class HazardEffects:
    inputs_base: SolveInputs
    zone_effects: Dict[str, ZoneEffect]
    door_effects: Dict[str, DoorEffect]
    exit_effects: Dict[str, ExitEffect]
    hazard_notes: Dict[str, List[str]]  # hazard id -> effect strings
    effective: Dict[str, bool]
    gas_locked_doors: Set[str]
    held: List[str]
    hazard_zone_types: Dict[str, str]  # zones with FIRE/SMOKE/GAS/CHEMICAL, for exposure and display
    advisories: List[str]
    assumptions: List[str]


def _bounding_doors(venue: VenueV2, zone_id: str) -> List[VenueDoor]:
    return [d for d in venue.doors if zone_id in d.zones]


def compute_effects(venue: VenueV2, hazards: List[dict], horizon: int) -> HazardEffects:
    """`hazards` entries need id, type, zone_id and untenable_s (already defaulted; None for WATER)."""
    dt = venue.time_step_seconds
    defaults = venue.hazard_defaults

    by_zone: Dict[str, List[dict]] = {}
    for hazard in hazards:
        by_zone.setdefault(hazard["zone_id"], []).append(hazard)

    effective: Dict[str, bool] = {}
    for zone_id, items in by_zone.items():
        top = max(PRECEDENCE[h["type"]] for h in items)
        for h in items:
            effective[h["id"]] = PRECEDENCE[h["type"]] == top

    no_entry: Dict[str, int] = {}
    untenable: Dict[str, int] = {}
    exit_closed: Dict[str, int] = {}
    mult: Dict[str, Tuple[float, float]] = {}
    door_fx: Dict[str, DoorEffect] = {d.id: DoorEffect() for d in venue.doors}
    exit_fx: Dict[str, ExitEffect] = {e.id: ExitEffect() for e in venue.exits}
    notes: Dict[str, List[str]] = {h["id"]: [] for h in hazards}
    zone_info: Dict[str, dict] = {}
    gas_locked: Set[str] = set()
    held: List[str] = []
    advisories: List[str] = []

    def set_mult(element: str, thr: float, trv: float) -> None:
        old = mult.get(element, (1.0, 1.0))
        mult[element] = (min(old[0], thr), max(old[1], trv))

    def hold(element_id: str) -> None:
        if element_id not in held:
            held.append(element_id)

    zone_name = {z.id: z.name for z in venue.zones}

    for hazard in hazards:
        kind, zone_id, hid = hazard["type"], hazard["zone_id"], hazard["id"]
        name = zone_name[zone_id]
        doors = _bounding_doors(venue, zone_id)
        zone_exits = [e for e in venue.exits if e.zone == zone_id]
        dflt = defaults.get(kind)
        T = hazard.get("untenable_s")
        if T is None and dflt is not None:
            T = dflt.untenable_s

        # Safety locks are unions across all hazards, effective or not.
        if kind == "GAS":
            for door in doors:
                fx = door_fx[door.id]
                fx.entry_denied_into.add(zone_id)
                fx.gas_held = True
                fx.reasons.append(f"Gas in {name}: lamp held static red; nothing is switched near the gas")
                hold(door.id)
                if door.actuation in LOCKABLE:
                    fx.gas_locked = True
                    gas_locked.add(door.id)
                    fx.reasons.append(f"Locked in its default state ({door.default_state}) because of gas in {name}")
            for ex in zone_exits:
                efx = exit_fx[ex.id]
                efx.unsafe = True
                efx.gas = True
                efx.reasons.append(f"Gas in {name}: exit closed, lamp held static red")
                hold(ex.id)
            notes[hid].append(f"Gas in {name}: no entry, no door opened or released"
                              + (", zone exits closed" if zone_exits else "") + ", lights held static red")
            advisories.append(f"Gas in {name}: ventilate to the outside manually; operate no switches nearby.")
            if door_servo := [d.id for d in doors if d.actuation in LOCKABLE]:
                notes[hid].append("Locked in default state: " + ", ".join(sorted(door_servo)))

        if not effective[hid]:
            notes[hid].append("Not effective: a higher-precedence hazard decides this zone; only safety locks still apply")
            continue

        if kind in ("FIRE", "CHEMICAL", "SMOKE", "GAS"):
            no_entry[zone_id] = 0
            if T is not None:
                untenable[zone_id] = min(untenable.get(zone_id, T), T)
            for door in doors:
                door_fx[door.id].entry_denied_into.add(zone_id)
        info = zone_info.setdefault(zone_id, {"types": [], "thr": None, "T": None})
        info["types"].append(kind)
        if kind != "WATER" and T is not None:
            info["T"] = T if info["T"] is None else min(info["T"], T)

        if kind in ("FIRE", "CHEMICAL"):
            for door in doors:
                if door.actuation == "hold_open":
                    fx = door_fx[door.id]
                    fx.released = True
                    fx.reasons.append(f"{kind.title()} in {name}: hold-open door released, closed to entry into {name}; "
                                      f"egress from {name} still modeled until untenable at {T} s")
            for ex in zone_exits:
                exit_closed[ex.id] = 0
                exit_fx[ex.id].unsafe = True
                exit_fx[ex.id].reasons.append(f"{kind.title()} in {name}: exit unsafe")
            notes[hid].append(f"No entry into {name}; untenable at {T} s; hold-open doors released; zone exits unsafe")
            if kind == "CHEMICAL":
                advisories.append(f"Chemical spill in {name}: confine it by closing the bounding doors to entry and deny entry.")
        elif kind == "SMOKE":
            thr = dflt.throughput_multiplier if dflt and dflt.throughput_multiplier else 0.5
            info["thr"] = thr if info["thr"] is None else min(info["thr"], thr)
            for door in doors:
                set_mult(door.id, thr, 1.0)
                if door.actuation == "hold_open":
                    fx = door_fx[door.id]
                    fx.released = True
                    fx.reasons.append(f"Smoke in {name}: hold-open door released, closed to entry into {name}; "
                                      f"egress still modeled until untenable at {T} s")
            # The sign over a smoke-logged exit shows a red X from detection, so the model closes the exit
            # from 0 as well: a plan never counts people through an exit it tells them not to use.
            for ex in zone_exits:
                set_mult(ex.id, thr, 1.0)
                exit_closed[ex.id] = 0
                exit_fx[ex.id].unsafe = True
                exit_fx[ex.id].reasons.append(f"Smoke in {name}: exit unsafe")
            notes[hid].append(f"No entry into {name}; throughput x{thr:g} on bounding doors and exits; untenable at {T} s")
        elif kind == "GAS":
            for ex in zone_exits:
                exit_closed[ex.id] = 0
            notes[hid].append(f"No entry into {name}; untenable at {T} s")
        elif kind == "WATER":
            thr = dflt.throughput_multiplier if dflt and dflt.throughput_multiplier else 0.5
            trv = dflt.travel_multiplier if dflt and dflt.travel_multiplier else 2.0
            info["thr"] = thr if info["thr"] is None else min(info["thr"], thr)
            for door in doors:
                set_mult(door.id, thr, trv)
            for ex in zone_exits:
                set_mult(ex.id, thr, trv)
            notes[hid].append(f"Passable but slowed: throughput x{thr:g}, travel x{trv:g} on bounding doors and exits")

    # Zone status table
    zone_effects: Dict[str, ZoneEffect] = {}
    hazard_zone_types: Dict[str, str] = {}
    for zone in venue.zones:
        items = by_zone.get(zone.id, [])
        if not items:
            zone_effects[zone.id] = ZoneEffect(zone.id, "passable", None, None, None)
            continue
        shown = max((h["type"] for h in items), key=lambda k: DISPLAY_RANK[k])
        info = zone_info.get(zone.id, {"types": [], "thr": None, "T": None})
        if any(k in HAZARDOUS for k in (h["type"] for h in items)):
            hazard_zone_types[zone.id] = max((h["type"] for h in items if h["type"] in HAZARDOUS),
                                             key=lambda k: DISPLAY_RANK[k])
        status = "slowed" if shown == "WATER" else "no_entry"
        zone_effects[zone.id] = ZoneEffect(zone.id, status, shown, untenable.get(zone.id), info["thr"])

    base = SolveInputs(closed_doors=frozenset(), no_entry_from=no_entry, untenable_at=untenable,
                       exit_closed_from=exit_closed, multipliers=mult)
    return HazardEffects(
        inputs_base=base, zone_effects=zone_effects, door_effects=door_fx, exit_effects=exit_fx,
        hazard_notes=notes, effective=effective, gas_locked_doors=gas_locked, held=held,
        hazard_zone_types=hazard_zone_types, advisories=list(dict.fromkeys(advisories)),
        assumptions=[venue_model_line(venue)] + MODEL_ASSUMPTIONS[1:])
