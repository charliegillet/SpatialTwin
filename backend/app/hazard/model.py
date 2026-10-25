"""Strict hazard schedule model and the read-only context handed to hazard tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Mapping, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from backend.app.contracts import AlternativeId, EvaluationEnvelope, RunContext
from backend.app.planner.model import VenueGraph

MAX_EVENTS = 6


class HazardToolError(Exception):
    """Carries only a fixed application code; the message is the code itself."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ToolContext:
    venue: VenueGraph
    base_context: RunContext
    envelopes: Mapping[AlternativeId, EvaluationEnvelope] = field(default_factory=dict)
    horizon_seconds: int = 0
    time_step_seconds: int = 0
    blocked_portals: FrozenSet[str] = frozenset()
    blocked_boundaries: FrozenSet[str] = frozenset()
    p3_physical_open: bool = False

    def __post_init__(self) -> None:
        if self.horizon_seconds <= 0:
            object.__setattr__(self, "horizon_seconds", self.venue.default_horizon_seconds)
        if self.time_step_seconds <= 0:
            object.__setattr__(self, "time_step_seconds", self.venue.time_step_seconds)


class HazardEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    element_id: str = Field(..., min_length=1, max_length=32)
    close_at_s: int = Field(..., ge=0)
    hazard_zone_ids: Tuple[str, ...] = Field(default=(), max_length=8)


class HazardSchedule(BaseModel):
    """1..6 closure events with unique element ids, validated against a venue and horizon.

    Validation context (``model_validate(..., context={"ctx": ToolContext})``) is required;
    without it only the structural rules apply and ``validate_against`` must be called.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    events: Tuple[HazardEvent, ...] = Field(..., min_length=1, max_length=MAX_EVENTS)

    @model_validator(mode="after")
    def unique_elements(self) -> "HazardSchedule":
        ids = [e.element_id for e in self.events]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate_element_id")
        return self

    @model_validator(mode="after")
    def context_rules(self, info: ValidationInfo) -> "HazardSchedule":
        ctx = (info.context or {}).get("ctx") if info.context else None
        if ctx is not None:
            self.validate_against(ctx)
        return self

    def validate_against(self, ctx: ToolContext) -> None:
        dt, horizon = ctx.time_step_seconds, ctx.horizon_seconds
        if dt <= 0 or horizon <= 0:
            raise ValueError("invalid_time_step")
        for e in self.events:
            if e.element_id not in ctx.venue.portals and e.element_id not in ctx.venue.boundaries:
                raise ValueError("unknown_element_id")
            if e.close_at_s % dt:
                raise ValueError("invalid_close_time")
            if e.close_at_s >= horizon:
                raise ValueError("close_time_beyond_horizon")
            if any(z not in ctx.venue.zones for z in e.hazard_zone_ids):
                raise ValueError("unknown_zone_id")

    @property
    def hazard_zone_ids(self) -> Tuple[str, ...]:
        seen = []
        for e in self.events:
            for z in e.hazard_zone_ids:
                if z not in seen:
                    seen.append(z)
        return tuple(seen)
