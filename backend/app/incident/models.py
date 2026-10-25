"""Typed request/response models for /api/incident. Field names are the frontend contract (docs/plans/contracts/incident.md)."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.app.venues.model import VENUE_ID_PATTERN
from backend.app.venues.schemas import HazardInput

Applied = Literal["open", "closed", "moving", "unknown", "sign"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HazardsRequest(_Strict):
    venue_id: str = Field(pattern=VENUE_ID_PATTERN)
    expected_plan_revision: int = Field(ge=0)
    hazards: List[HazardInput]


class ApproveRequest(_Strict):
    plan_revision: int = Field(ge=0)
    candidate_hash: str = Field(min_length=1, max_length=128)
    door_states: Dict[str, Literal["open", "closed"]]


class FaultRequest(_Strict):
    # heartbeat_timeout is controller-wide, so its gate_id is optional (and ignored).
    gate_id: Optional[str] = Field(default=None, max_length=32)
    fault: Literal["stall", "switch_disagreement", "dropped_ack", "heartbeat_timeout"]


class ClearFaultRequest(_Strict):
    gate_id: Optional[str] = Field(default=None, max_length=32)


class PlanDoorView(_Strict):
    id: str
    state: Literal["open", "closed"]
    lamp: str
    actuation: str
    controllable: bool
    changed: bool
    stuck: bool
    decided_by: str
    reason: str
    # What the world shows now: only an endpoint observation says "open"/"closed" for a gate; signs follow the plan.
    applied: Applied


class PlanExitView(_Strict):
    id: str
    zone: str
    safe: bool
    lamp: str
    modeled_crossings: int
    reason: str


class IncidentPlan(_Strict):
    plan_id: str
    plan_revision: int
    candidate_hash: str
    label: Literal["primary", "fallback"]
    note: Optional[str] = None
    reason: str
    valid: bool
    status: str
    initial_population: int
    completed_crossings: int
    baseline_completed: int
    no_hazard_completed: int
    door_states: Dict[str, Literal["open", "closed"]]
    doors: List[PlanDoorView]
    exits: List[PlanExitView]
    lights_px: str
    stuck_doors: List[str]
    advisories: List[str]
    announcement: str
    count_label: str = "modeled crossings"
    created_at: str


class ApprovalRecord(_Strict):
    approval_id: str
    plan_revision: int
    candidate_hash: str
    door_states: Dict[str, str]
    status: Literal["actuating", "applied", "failed"]
    commands: Dict[str, str]
    results: Dict[str, str]
    reason: Optional[str] = None
    fallback_plan_revision: Optional[int] = None
    started_at: str
    finished_at: Optional[str] = None
    simulated: bool = True


class IncidentState(_Strict):
    simulated: bool = True
    venue_id: str
    geometry_revision: str
    plan_revision: int
    hazards: List[Dict[str, Any]]
    plan: Optional[IncidentPlan]
    plan_error: Optional[str] = None
    controller: Dict[str, Any]
    stuck_doors: List[str]
    approvals: List[ApprovalRecord]
    approval_in_progress: bool
    last_event_id: int
