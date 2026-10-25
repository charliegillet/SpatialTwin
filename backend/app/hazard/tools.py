"""Read-only hazard tools for the managed agent. Results come only from checker output."""
from __future__ import annotations

import json
from typing import Any, Dict

from pydantic import ValidationError

from backend.app.contracts import AlternativeId

from .exposure import EXPOSURE_LABEL, modeled_exposure_people_seconds
from .model import HazardSchedule, HazardToolError, ToolContext
from .schedule import solve_schedule

_ARGS_SCHEMA = {
    "type": "object",
    "properties": {
        "alternative_id": {"type": "string", "enum": ["KEEP_CURRENT", "OPEN_P3"]},
        "events": {
            "type": "array", "minItems": 1, "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "string", "enum": ["P1", "P2", "P3", "B1", "B2"]},
                    "close_at_s": {"type": "integer", "minimum": 0},
                    "hazard_zone_ids": {"type": "array", "maxItems": 4,
                                        "items": {"type": "string", "enum": ["EVENT", "WEST", "EAST", "RESERVE"]}},
                },
                "required": ["element_id", "close_at_s", "hazard_zone_ids"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["alternative_id", "events"],
    "additionalProperties": False,
}

HAZARD_TOOL_DEFINITIONS = [
    {"type": "function", "name": "simulate_hazard_schedule",
     "description": "Evaluate timed element closures (forecast model, closure times known in advance) with the local checker.",
     "parameters": _ARGS_SCHEMA},
    {"type": "function", "name": "score_exposure",
     "description": "Same as simulate_hazard_schedule, and report modeled people-seconds in the declared hazard zones; "
                    "modeled, not a casualty or survival prediction.",
     "parameters": _ARGS_SCHEMA},
]
_NAMES = frozenset(d["name"] for d in HAZARD_TOOL_DEFINITIONS)


def _parse(args: Any, ctx: ToolContext) -> tuple[AlternativeId, HazardSchedule]:
    if type(args) is not dict or set(args) != {"alternative_id", "events"}:
        raise HazardToolError("invalid_arguments")
    alt = args["alternative_id"]
    if type(alt) is not str or alt not in AlternativeId.__members__:
        raise HazardToolError("invalid_arguments")
    try:
        schedule = HazardSchedule.model_validate_json(
            json.dumps({"events": args["events"]}), strict=True, context={"ctx": ctx})
    except (ValidationError, ValueError, TypeError):
        raise HazardToolError("invalid_arguments") from None
    return AlternativeId(alt), schedule


def execute_hazard_tool(name: str, args: Any, ctx: ToolContext) -> Dict[str, Any]:
    if type(name) is not str or name not in _NAMES:
        raise HazardToolError("unknown_tool")
    alt, schedule = _parse(args, ctx)
    try:
        env = solve_schedule(schedule, ctx, alt)
        report = env.validator_report
        zones = schedule.hazard_zone_ids
        if name == "score_exposure":
            exposure, label = modeled_exposure_people_seconds(
                env.timeline, zones, env.time_step_seconds, env.initial_population, ctx.venue.zones)
        else:
            exposure, label = None, EXPOSURE_LABEL
    except HazardToolError:
        raise
    except Exception:
        raise HazardToolError("evaluation_failed") from None
    baseline = ctx.envelopes.get(alt)
    return {
        "tool": name,
        "alternative_id": alt.value,
        "is_valid": report.is_valid,
        "reasons": list(report.reasons),
        "status": env.status.value,
        "completed_crossings": env.completed_crossings,
        "remaining_population": env.remaining_population,
        "baseline_completed_crossings": baseline.completed_crossings if baseline is not None else None,
        "modeled_exposure_people_seconds": exposure,
        "exposure_label": label,
    }
