"""Request/response models for POST /api/venues/building-v2/door-plan.

Field names mirror frontend/src/twin/types.ts exactly (DoorPlanRequest, DoorPlanResponse and nested types).
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

HazardType = Literal["FIRE", "SMOKE", "GAS", "CHEMICAL", "WATER"]
DoorActuation = Literal["hold_open", "simulated_servo", "motorized", "indicator_only", "fixed"]
DoorLamp = Literal["green", "red", "red_static", "off"]
ExitLamp = Literal["green_flash", "green", "red_x", "red_static"]
DecidedBy = Literal["default", "hazard_rule", "door_planner", "gas_lock"]
LightCode = Literal["F", "g", "X", "S", "O", "B", "L", "0"]
PlanStatus = Literal["COMPLETE_WITHIN_MODEL", "PARTIAL_WITHIN_HORIZON", "NO_FEASIBLE_EXIT", "SOLVER_INFEASIBLE"]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Position(_Request):
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class HazardInput(_Request):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    type: HazardType
    position: Position
    zone_id: Optional[str] = None
    source: Literal["simulated", "camera"]
    untenable_s: Optional[float] = Field(default=None, allow_inf_nan=False)
    proposal_id: Optional[str] = Field(default=None, max_length=128)


class DoorPlanRequest(_Request):
    hazards: List[HazardInput]
    horizon_seconds: Optional[float] = Field(default=None, allow_inf_nan=False)


class HazardEcho(BaseModel):
    id: str
    type: HazardType
    position: Position
    zone_id: str
    source: Literal["simulated", "camera"]
    untenable_s: Optional[int] = None
    proposal_id: Optional[str] = None
    effective: bool
    effects: List[str]
    # Provenance of the confirmed camera read this hazard came from (None for simulated hazards).
    camera_provenance: Optional[Literal["live", "fixture"]] = None


class PlanDoor(BaseModel):
    id: str
    state: Literal["open", "closed"]
    lamp: DoorLamp
    entry_denied_into: List[str]
    reason: str
    actuation: DoorActuation
    changed: bool
    locked: bool
    decided_by: DecidedBy


class PlanExit(BaseModel):
    id: str
    zone: str
    safe: bool
    lamp: ExitLamp
    reason: str
    modeled_crossings: int


class PlanZone(BaseModel):
    id: str
    status: Literal["passable", "slowed", "no_entry"]
    hazard_type: Optional[HazardType] = None
    untenable_at_s: Optional[int] = None
    throughput_multiplier: Optional[float] = None
    initial_occupants: int
    remaining_at_horizon: int


class PlanRoute(BaseModel):
    origin: str
    path: List[str]
    via_doors: List[str]
    exit_id: str
    people: int
    slowed: bool


class TimelineFrameV2(BaseModel):
    step: int
    time_seconds: int
    occupancy: Dict[str, int]
    exits_cumulative: Dict[str, int]
    in_transit: int
    total_completed: int


class ValidatorReportV2(BaseModel):
    is_valid: bool
    checks_run: List[str]
    reasons: List[str]


class PlanOutcome(BaseModel):
    run_id: str
    candidate_hash: str
    status: PlanStatus
    initial_population: int
    completed_crossings: int
    remaining_population: int
    horizon_seconds: int
    time_step_seconds: int
    exit_breakdown: Dict[str, int]
    timeline: List[TimelineFrameV2]
    validator_report: ValidatorReportV2
    modeled_exposure_people_seconds: int
    exposure_label: str


class PlanAlternative(BaseModel):
    door_states: Dict[str, Literal["open", "closed"]]
    completed_crossings: int
    modeled_exposure_people_seconds: int
    is_valid: bool
    rank: int
    run_id: str


class LightSegment(BaseModel):
    element_id: str
    range: List[int]
    code: LightCode


class PlanLights(BaseModel):
    px: str
    segments: List[LightSegment]
    held: List[str]


class Baseline(BaseModel):
    completed_crossings: int
    run_id: str


class DoorPlanResponse(BaseModel):
    plan_id: str
    venue_id: Literal["building-v2"]
    geometry_revision: str
    hypothetical: Literal[True] = True
    provenance: Literal["local_door_planner_v1"] = "local_door_planner_v1"
    hazards: List[HazardEcho]
    doors: List[PlanDoor]
    exits: List[PlanExit]
    zones: List[PlanZone]
    routes: List[PlanRoute]
    chosen: PlanOutcome
    baseline: Baseline
    no_hazard_completed: int
    alternatives: List[PlanAlternative]
    lights: PlanLights
    advisories: List[str]
    announcement: str
    model_assumptions: List[str]
    timings_ms: float
