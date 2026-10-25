"""Typed public intake: preserve the original capture context and timestamp."""
from typing import Literal, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.app.contracts import EntityType, RunContext, TargetId


class GroundingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capture_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    timestamp_iso: str = Field(max_length=64)
    source_context: RunContext
    dimensions: Tuple[int, int] = (1920, 1080)
    source_kind: Literal["tabletop_camera", "annotated_plan", "fixture"] = "tabletop_camera"
    image_base64: Optional[str] = Field(default=None, max_length=7_000_000)
    image_sha256: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    thinking_level: Literal["low", "medium", "high"] = "low"
    mode: Literal["live", "fixture"] = "live"
    fixture_target: Optional[Literal["P1", "P2", "B2", "ambiguous", "no_match"]] = None
    deadline_seconds: float = Field(default=20.0, gt=0, le=60, allow_inf_nan=False)


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_context: RunContext
    investigation_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    mode: Literal["live", "local"] = "live"
    deadline_seconds: float = Field(default=60.0, gt=0, le=60, allow_inf_nan=False)


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["APPLY_BLOCKAGE", "CLEAR_BLOCKAGE", "RESET_SCENARIO"]
    expected_context: RunContext
    expected_scenario_revision: int = Field(gt=0)
    idempotency_key: str = Field(min_length=1, max_length=128)
    target_type: Optional[EntityType] = None
    target_id: Optional[TargetId] = None
    source: Literal["grounding_proposal", "manual_override", "replay"] = "manual_override"
    proposal_id: Optional[str] = Field(default=None, max_length=128)
    reviewed: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def explicit_target(self):
        if self.type != "RESET_SCENARIO" and (self.target_id is None or self.target_type is None):
            raise ValueError("An explicit target is required")
        return self


class GateApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_context: RunContext
    expected_scenario_revision: Optional[int] = Field(default=None, gt=0)
    candidate_alternative: Literal["OPEN_P3"] = "OPEN_P3"
    investigation_id: str = Field(min_length=1, max_length=128)
    candidate_run_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)


class InvestigationCancellationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_context: RunContext
