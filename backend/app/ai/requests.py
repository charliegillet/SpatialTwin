"""Typed public intake: preserve the original capture context and timestamp."""
from datetime import datetime
from typing import Literal, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from backend.app.contracts import EntityType, RunContext, TargetId

MAX_DIMENSION = 8192


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
    media_kind: Literal["image", "video"] = "image"
    video_mode: Literal["static", "agentic"] = "static"
    video_base64: Optional[str] = Field(default=None, max_length=12_000_000)
    video_mime: Literal["video/mp4", "video/webm"] = "video/mp4"
    video_duration_seconds: Optional[float] = Field(default=None, ge=0, le=3600, allow_inf_nan=False)

    @field_validator("timestamp_iso")
    @classmethod
    def timestamp_is_aware_iso(cls, value: str) -> str:
        # Parsed here so later staleness checks never meet an unparseable or timezone-less capture time.
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("timestamp_iso must be an ISO-8601 timestamp") from None
        if parsed.tzinfo is None:
            raise ValueError("timestamp_iso must include a timezone")
        return value

    @field_validator("dimensions")
    @classmethod
    def dimensions_are_bounded(cls, value: Tuple[int, int]) -> Tuple[int, int]:
        if any(not 1 <= side <= MAX_DIMENSION for side in value):
            raise ValueError(f"dimensions must be between 1 and {MAX_DIMENSION}")
        return value


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
