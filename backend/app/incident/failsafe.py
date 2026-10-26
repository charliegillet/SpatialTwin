"""The unattended fail-safe: what the incident may do when nobody approves a checked plan in time.

Off by default: a person approves every door move. Armed, every new checked plan gives a person a window (15 s by
default). If nobody approves, changes the hazards or disarms ("I'm here") in that window, the fail-safe approves the
plan itself, with two rules a person would not need:

* it never opens a gate into a room with a hazard (a no-entry room): every such gate is held closed and the plan is
  re-checked without them, so what moves is a plan the checker accepted with those gates shut;
* it never trusts a gate whose position is unknown: a FAULT/UNKNOWN gate is treated as stuck closed.

Everything else is the normal path: the checker decides every number, ACK is not arrival, a jam re-plans to a fallback
(which gets the same window). The pure helpers live here; the timer and the approval are in IncidentManager.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Mapping, Set

from backend.app.venues.schemas import DoorPlanResponse

DEFAULT_WINDOW_SECONDS = 15.0


def deadline_iso(seconds_from_now: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds_from_now)).isoformat(timespec="milliseconds")


def gates_into_hazard(door_plan: DoorPlanResponse, gate_ids: Iterable[str], excluded: Set[str]) -> Dict[str, List[str]]:
    """Gates that border a no-entry room (fire, smoke, gas or chemical) -> those rooms. Stuck (or doubtful) gates are
    already held closed, and a locked gate is never switched (nothing is switched near gas)."""
    gates = set(gate_ids)
    return {d.id: sorted(d.entry_denied_into) for d in door_plan.doors
            if d.id in gates and d.id not in excluded and d.entry_denied_into and not d.locked}


def left_open(door_states: Mapping[str, str], risky: Mapping[str, List[str]]) -> List[str]:
    """The risky gates a plan would have open: opened by the planner, or open by default."""
    return sorted(gate for gate in risky if door_states.get(gate) == "open")


def join_ids(items: List[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# Spoken before the plan's own announcement. Says what happened, not that everyone is safe.
SPOKEN_PREFIX = "Nobody approved in time. The fail-safe approved the checked plan."
_PLANNED = re.compile(r"Door (\S+) between (.+?) is to be opened\.")


def spoken_text(announcement: str, commands: Mapping[str, str]) -> str:
    """What the fail-safe says: the prefix, then the plan's announcement with each door it is opening now worded as
    "is opening" (never "is open": that needs the endpoint switch, and the clip is made before the door arrives)."""
    body = _PLANNED.sub(lambda m: f"Door {m.group(1)} between {m.group(2)} is opening." if commands.get(m.group(1)) == "OPEN"
                        else m.group(0), (announcement or "").strip())
    return f"{SPOKEN_PREFIX} {body}".strip()


def held_reason(door_id: str, rooms: List[str]) -> str:
    return (f"{door_id} held closed by the fail-safe: it opens into {join_ids(rooms)}, a room with a hazard; "
            "a person can take over (I'm here) and approve opening it")
