"""Plain-language announcement text derived only from a checked building-v2 door plan.

The text restates what the plan already says (hazard rooms, unsafe exits, exits carrying modeled
flow, doors the planner opened, the gas no-switching rule). It adds no new claim, never mentions
survival, and is empty when there is no hazard. The UI labels it as a simulated announcement.
"""
from __future__ import annotations

from typing import Dict, Iterable, List

HAZARD_WORDS = {"FIRE": "Fire", "SMOKE": "Smoke", "GAS": "A gas leak", "CHEMICAL": "A chemical spill", "WATER": "Water"}


def _place(name: str) -> str:
    return name if name.startswith("Room") else "the " + name.lower()


def _join(items: List[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " or " + items[-1]


def build_announcement(zone_names: Dict[str, str], exit_names: Dict[str, str], hazards: Iterable[dict],
                       exits: Iterable[dict], doors: Iterable[dict]) -> str:
    """hazards: {type, zone_id, effective}; exits: {id, safe, modeled_crossings}; doors: {id, zones, decided_by, state}."""
    hazards = [h for h in hazards if h["effective"]]
    if not hazards:
        return ""
    seen = set()
    sentences: List[str] = []
    for h in hazards:
        key = (h["type"], h["zone_id"])
        if key in seen:
            continue
        seen.add(key)
        sentences.append(f"{HAZARD_WORDS[h['type']]} in {_place(zone_names[h['zone_id']])}.")
    exits = list(exits)
    unsafe = [exit_names[e["id"]].lower() for e in exits if not e["safe"]]
    if unsafe:
        sentences.append(f"Do not use the {_join(unsafe)}.")
    flowing = sorted((e for e in exits if e["safe"] and e["modeled_crossings"] > 0),
                     key=lambda e: (-e["modeled_crossings"], e["id"]))
    if flowing:
        sentences.append(f"Use the {_join([exit_names[e['id']].lower() for e in flowing])}.")
    for d in doors:
        if d["decided_by"] == "door_planner" and d["state"] == "open":
            a, b = (_place(zone_names[z]) for z in d["zones"])
            sentences.append(f"Door {d['id']} between {a} and {b} is open.")
    gas_rooms = [_place(zone_names[h["zone_id"]]) for h in hazards if h["type"] == "GAS"]
    if gas_rooms:
        sentences.append(f"Do not operate switches near {_join(sorted(set(gas_rooms)))}.")
    return " ".join(["Attention."] + sentences)
