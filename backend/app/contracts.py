"""
SpatialTwin Central Contracts & Protocol Envelopes
Contract version: v1.0.0
Owner: Codex / SpatialTwin core
"""

from __future__ import annotations
import hashlib
import json
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


# Canonical Target Identifiers
SUPPORTED_TARGET_PAIRS: List[Tuple[str, str]] = [
    ("portal", "P1"),
    ("portal", "P2"),
    ("boundary", "B2"),
]

SUPPORTED_TARGET_IDS = [f"{t}:{i}" for t, i in SUPPORTED_TARGET_PAIRS]


class EntityType(str, Enum):
    PORTAL = "portal"
    BOUNDARY = "boundary"


class TargetId(str, Enum):
    P1 = "P1"
    P2 = "P2"
    B2 = "B2"


class AlternativeId(str, Enum):
    KEEP_CURRENT = "KEEP_CURRENT"
    OPEN_P3 = "OPEN_P3"


class GroundingStatus(str, Enum):
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    NO_MATCH = "no_match"


class GateTarget(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class GateObservedState(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    TRANSIT = "TRANSIT"
    UNKNOWN = "UNKNOWN"
    FAULT = "FAULT"


# =====================================================================
# 1. Context and Provenance
# =====================================================================

class RunContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    geometry_revision: str = Field(..., min_length=1, max_length=128, description="Canonical geometry revision, e.g. 'geom-shack15-v1'")
    scenario_revision: int = Field(..., ge=1, description="Monotonically increasing scenario revision")
    physical_revision: int = Field(..., ge=1, description="Monotonically increasing physical revision")
    parameters_revision: str = Field(default="params-v1", description="Declared capacity and solver parameters revision")
    solver_version: str = Field(default="spatialtwin-flow-v1.1", description="Numerical solver implementation version")
    state_epoch: str = Field(default="legacy", min_length=1, max_length=128, description="Unique authoritative process session; old evidence cannot become current after restart")
    context_hash: Optional[str] = Field(default=None, description="Canonical SHA256 of context fields")

    @model_validator(mode="after")
    def canonical_hash(self) -> RunContext:
        expected = self.compute_hash()
        if self.context_hash is not None and self.context_hash != expected:
            raise ValueError("Context hash does not match its revisions")
        object.__setattr__(self, "context_hash", expected)
        return self

    def compute_hash(self) -> str:
        payload = [self.geometry_revision, self.scenario_revision, self.physical_revision,
                   self.parameters_revision, self.solver_version, self.state_epoch]
        return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest()

    def is_current(self, other: RunContext) -> bool:
        return (
            self.geometry_revision == other.geometry_revision
            and self.scenario_revision == other.scenario_revision
            and self.physical_revision == other.physical_revision
            and self.parameters_revision == other.parameters_revision
            and self.solver_version == other.solver_version
            and self.state_epoch == other.state_epoch
            and self.context_hash == other.context_hash == self.compute_hash() == other.compute_hash()
        )


class ScenarioLabRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_context: RunContext
    reserve_basis: Literal["reported", "closed_benchmark"] = "reported"


class Capture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capture_id: str
    timestamp_iso: str
    source_kind: Literal["tabletop_camera", "annotated_plan", "fixture"]
    dimensions: Tuple[int, int] = (1920, 1080)
    source_geometry_revision: str
    expected_scenario_revision: int
    expected_physical_revision: int
    image_base64: Optional[str] = None
    notes: Optional[str] = None
    source_context: Optional[RunContext] = None
    image_sha256: Optional[str] = None


# =====================================================================
# 2. Grounding Proposal
# =====================================================================

class GroundingProposalV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = "1.0.0"
    capture_id: str
    source_context: RunContext
    status: GroundingStatus
    candidate_ids: List[str] = Field(default_factory=lambda: list(SUPPORTED_TARGET_IDS))
    selected_entity_type: Optional[EntityType] = None
    selected_entity_id: Optional[str] = None
    operation: Literal["SET_UNAVAILABLE"] = "SET_UNAVAILABLE"
    evidence: str
    thinking_level: Literal["low", "medium", "high"] = "low"
    box_2d: Optional[List[StrictInt]] = Field(
        default=None,
        description="Normalized [ymin, xmin, ymax, xmax] coordinates on 0-1000 scale"
    )

    def validate_semantic_soundness(self) -> Tuple[bool, List[str]]:
        errors = []
        if len(set(self.candidate_ids)) != len(self.candidate_ids) or any(i not in SUPPORTED_TARGET_IDS for i in self.candidate_ids):
            errors.append("Candidate IDs must be unique members of the reviewed catalog")
        if self.box_2d is not None:
            b = self.box_2d
            if len(b) != 4 or any(type(v) is not int or not 0 <= v <= 1000 for v in b):
                errors.append("Bounding box requires four integers between 0 and 1000")
            elif b[0] >= b[2] or b[1] >= b[3]:
                errors.append("Bounding box coordinates must be ordered")
        if self.status == GroundingStatus.MATCHED:
            if not self.selected_entity_type or not self.selected_entity_id:
                errors.append("Matched status requires both selected_entity_type and selected_entity_id")
            else:
                pair = (self.selected_entity_type.value, self.selected_entity_id)
                if pair not in SUPPORTED_TARGET_PAIRS:
                    errors.append(f"Pair {pair} is not in allowlisted stage targets: {SUPPORTED_TARGET_PAIRS}")
                typed_id = f"{self.selected_entity_type.value}:{self.selected_entity_id}"
                if typed_id not in self.candidate_ids:
                    errors.append(f"Selected target {typed_id} is not present in candidate_ids {self.candidate_ids}")
        elif self.status == GroundingStatus.AMBIGUOUS:
            if self.selected_entity_id is not None or self.selected_entity_type is not None:
                errors.append("Ambiguous status must not contain an applied selected_entity_id")
        elif self.status == GroundingStatus.NO_MATCH:
            if self.selected_entity_id is not None or self.selected_entity_type is not None:
                errors.append("No_match status must not contain an applied selected_entity_id")
        return (len(errors) == 0, errors)


class GroundingResult(BaseModel):
    proposal: Optional[GroundingProposalV1] = None
    proposal_id: Optional[str] = None
    provenance: Literal["live", "fixture", "unavailable"] = "unavailable"
    status: Literal["completed", "failed", "unavailable", "timed_out", "cancelled"] = "unavailable"
    errors: List[str] = Field(default_factory=list)
    provider_interaction_id: Optional[str] = None
    provider_model: Optional[str] = None
    token_usage: Dict[str, int] = Field(default_factory=dict)
    latency_ms: float = 0.0
    sdk_version: Optional[str] = None


# =====================================================================
# 3. Numerical Solver & Evaluation Contracts
# =====================================================================

class ComputationStatus(str, Enum):
    COMPLETE_WITHIN_MODEL = "COMPLETE_WITHIN_MODEL"
    PARTIAL_WITHIN_HORIZON = "PARTIAL_WITHIN_HORIZON"
    NO_FEASIBLE_EXIT = "NO_FEASIBLE_EXIT"
    INVALID_INPUT = "INVALID_INPUT"
    SOLVER_TIMEOUT = "SOLVER_TIMEOUT"
    SOLVER_INFEASIBLE = "SOLVER_INFEASIBLE"
    STALE = "STALE"


class ValidatorReport(BaseModel):
    is_valid: bool
    checks_run: List[str]
    reasons: List[str]
    conservation_verified: bool
    unassigned_accounted: bool
    capacities_respected: bool
    quota_respected: bool


class EvaluationEnvelope(BaseModel):
    run_id: str
    base_context: RunContext
    candidate_hash: str
    alternative_id: AlternativeId
    status: ComputationStatus
    initial_population: int
    completed_crossings: int
    remaining_population: int
    horizon_seconds: int
    time_step_seconds: int
    boundary_breakdown: Dict[str, int] = Field(default_factory=dict)
    zone_occupancy: Dict[str, int] = Field(default_factory=dict)
    timeline: List[Dict[str, Any]] = Field(default_factory=list, description="Step-by-step occupancy and exit flow schedule")
    bottlenecks: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    validator_report: ValidatorReport
    timings_ms: float
    provenance: str = "fixed_numerical_flow_solver_v1"

    @property
    def is_publishable(self) -> bool:
        return self.validator_report.is_valid and self.status in (
            ComputationStatus.COMPLETE_WITHIN_MODEL,
            ComputationStatus.PARTIAL_WITHIN_HORIZON,
            ComputationStatus.NO_FEASIBLE_EXIT,
        )


# =====================================================================
# 4. Managed Agent Investigation Contracts
# =====================================================================

class InvestigationStatus(str, Enum):
    COMPLETED = "completed"
    REQUIRES_ACTION = "requires_action"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    CANCELLED = "cancelled"
    IN_PROGRESS = "in_progress"
    TIMED_OUT = "timed_out"


class ToolCallLedgerEntry(BaseModel):
    call_id: str
    function_name: str
    arguments: Dict[str, Any]
    status: Literal["requested", "executed", "failed", "duplicate"]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float


class InvestigationResult(BaseModel):
    investigation_id: str
    base_context: RunContext
    configured_agent: str = "antigravity-preview-09-2026"
    configured_model: str = "gemini-4-argon"
    status: InvestigationStatus
    candidate_envelopes: List[EvaluationEnvelope] = Field(default_factory=list)
    recommended_alternative: Optional[AlternativeId] = None
    tool_ledger: List[ToolCallLedgerEntry] = Field(default_factory=list)
    agent_explanation: str
    token_usage: Dict[str, int] = Field(default_factory=dict)
    deadline_seconds: float = 60.0
    errors: List[str] = Field(default_factory=list)
    provenance: Literal["live", "local", "unavailable"] = "unavailable"
    provider_interaction_id: Optional[str] = None
    provider_environment_id: Optional[str] = None
    provider_model: Optional[str] = None
    sdk_version: Optional[str] = None
    latency_ms: float = 0.0
    replayed: bool = False
    last_provider_status: Optional[str] = None
    provider_progress: List[Dict[str, Any]] = Field(default_factory=list)


# =====================================================================
# 5. Hardware Serial Bridge Protocol (v: 1)
# =====================================================================

class SerialCommandType(str, Enum):
    HELLO = "HELLO"
    HEARTBEAT = "HEARTBEAT"
    READ_STATE = "READ_STATE"
    ARM = "ARM"
    SET_GATE_TARGET = "SET_GATE_TARGET"
    SET_DISPLAY = "SET_DISPLAY"
    STOP_OUTPUTS = "STOP_OUTPUTS"


class SerialResponseType(str, Enum):
    HELLO_ACK = "HELLO_ACK"
    ACK = "ACK"
    OBSERVATION = "OBSERVATION"
    FAULT = "FAULT"


class HostCommandEnvelope(BaseModel):
    v: int = 1
    type: SerialCommandType
    session_id: str
    command_id: str
    expected_boot_id: Optional[str] = None
    expected_gate_epoch: Optional[int] = None
    scenario_revision: Optional[int] = None
    calibration_id: Optional[str] = None
    gate_id: Optional[str] = None
    target: Optional[GateTarget] = None
    display_pixels: Optional[List[int]] = None  # 24 RGB 3-tuples or packed ints


class DeviceObservation(BaseModel):
    v: int = 1
    type: SerialResponseType = SerialResponseType.OBSERVATION
    boot_id: str
    seq: int
    gate_epoch: int
    gate_id: str = "G1"
    state: GateObservedState
    open_switch: bool       # True = pressed (active)
    closed_switch: bool     # True = pressed (active)
    command_id: Optional[str] = None
    fault: Optional[str] = None


# =====================================================================
# 6. Authoritative Scenario Commands
# =====================================================================

class ApplyBlockageCommand(BaseModel):
    scenario_id: str = "facility-demo"
    expected_scenario_revision: int
    idempotency_key: str
    target_type: EntityType
    target_id: TargetId
    source: Literal["grounding_proposal", "manual_override", "replay"] = "grounding_proposal"
    expected_context: Optional[RunContext] = None
    proposal_id: Optional[str] = None
    reviewed: bool = False


class ClearBlockageCommand(BaseModel):
    scenario_id: str = "facility-demo"
    expected_scenario_revision: int
    idempotency_key: str
    target_type: EntityType
    target_id: TargetId
    expected_context: Optional[RunContext] = None


class ResetScenarioCommand(BaseModel):
    scenario_id: str = "facility-demo"
    expected_scenario_revision: int
    idempotency_key: str
    expected_context: Optional[RunContext] = None


class OperatorPhysicalApprovalCommand(BaseModel):
    scenario_id: str = "facility-demo"
    expected_scenario_revision: int
    expected_physical_revision: int
    candidate_alternative: AlternativeId = AlternativeId.OPEN_P3
    operator_signature: str = "operator_confirmed"
    idempotency_key: str


# =====================================================================
# Hazard simulation route contracts
# =====================================================================

class HazardEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    element_id: str = Field(min_length=1, max_length=32)
    close_at_s: StrictInt = Field(ge=0)


class HazardScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alternative_id: AlternativeId
    events: List[HazardEventRequest] = Field(min_length=1, max_length=6)


class HazardResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str
    alternative_id: AlternativeId
    is_valid: bool
    reasons: List[str]
    status: str
    completed_crossings: int
    remaining_population: int
    baseline_completed_crossings: Optional[int] = None
    modeled_exposure_people_seconds: Optional[float] = None
    exposure_label: str
