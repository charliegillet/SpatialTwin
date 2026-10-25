"""Read-only review basis: one accepted checked run plus reported state.

Review code re-reads the published envelope against the reviewed venue spec.
It never calls the solver, a provider or the hardware bridge.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict

from backend.app.contracts import AlternativeId, EvaluationEnvelope, GateObservedState, RunContext
from backend.app.planner.model import VenueGraph

HardwareMode = Literal["simulator", "physical_serial", "unknown"]

# Timeline field names are part of the published envelope contract.
ZONE_FIELDS = {"EVENT": "event_occupancy", "WEST": "west_occupancy",
               "EAST": "east_occupancy", "RESERVE": "reserve_occupancy"}
BOUNDARY_FIELDS = {"B1": "b1_cumulative", "B2": "b2_cumulative"}
COUNT_FIELDS = (*ZONE_FIELDS.values(), "in_transit_occupancy", *BOUNDARY_FIELDS.values(), "total_completed")
REQUIRED_CHECKS = (
    "population_conservation", "boundary_quota_limits", "residual_occupant_accounting",
    "zone_storage_capacities", "timeline_population_conservation", "timeline_boundary_rates",
    "timeline_matches_flow",
)
OBSERVED_GATE_STATES = (GateObservedState.OPEN, GateObservedState.CLOSED)


class ReviewUnavailable(Exception):
    """Carries only a fixed application diagnostic code."""


class EvidencePointer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source: Literal["checked_plan", "venue_spec", "reported_state", "investigation"]
    ref: str
    field: str


Frame = Mapping[str, int]


@dataclass(frozen=True)
class ReviewBasis:
    context: RunContext
    plan: Optional[EvaluationEnvelope]
    venue: VenueGraph
    blocked_portals: frozenset
    blocked_boundaries: frozenset
    gate_state: GateObservedState
    hardware_boot_id: Optional[str]
    gate_epoch: int
    hardware_mode: HardwareMode

    def plan_pointer(self, field: str) -> EvidencePointer:
        return EvidencePointer(source="checked_plan", ref=self.plan.run_id, field=field)

    def venue_pointer(self, field: str) -> EvidencePointer:
        return EvidencePointer(source="venue_spec", ref=self.venue.geometry_revision, field=field)

    def state_pointer(self, field: str) -> EvidencePointer:
        return EvidencePointer(source="reported_state", ref=self.context.context_hash, field=field)


def snapshot_basis(state_manager: Any, hardware_mode: str) -> ReviewBasis:
    """Copy one consistent view under the authoritative state lock."""
    with state_manager._state_lock:
        return ReviewBasis(
            context=state_manager.get_current_context(),
            plan=state_manager.current_plan.model_copy(deep=True) if state_manager.current_plan else None,
            venue=state_manager.venue_graph.model_copy(deep=True),
            blocked_portals=frozenset(state_manager.blocked_portals),
            blocked_boundaries=frozenset(state_manager.blocked_boundaries),
            gate_state=state_manager.physical_gate_state,
            hardware_boot_id=state_manager.last_hardware_boot_id,
            gate_epoch=state_manager.last_gate_epoch,
            hardware_mode=hardware_mode if hardware_mode in ("simulator", "physical_serial") else "unknown",
        )


def _count(value: Any) -> bool:
    return type(value) is int and value >= 0


def checked_frames(basis: ReviewBasis) -> Tuple[Frame, ...]:
    """Fail closed unless the accepted run is current, checker-accepted and self-consistent."""
    plan = basis.plan
    if plan is None:
        raise ReviewUnavailable("no_checked_plan")
    if plan.alternative_id != AlternativeId.KEEP_CURRENT:
        raise ReviewUnavailable("plan_not_accepted_layout")
    if not plan.base_context.is_current(basis.context):
        raise ReviewUnavailable("stale_plan")
    if basis.venue.geometry_revision != basis.context.geometry_revision:
        raise ReviewUnavailable("geometry_mismatch")
    report = plan.validator_report
    if not plan.is_publishable or not report.is_valid or report.reasons:
        raise ReviewUnavailable("plan_rejected_by_checker")
    if any(check not in report.checks_run for check in REQUIRED_CHECKS):
        raise ReviewUnavailable("checker_evidence_incomplete")
    if set(basis.venue.zones) - set(ZONE_FIELDS) or set(basis.venue.boundaries) - set(BOUNDARY_FIELDS):
        raise ReviewUnavailable("unsupported_geometry")
    horizon, step = plan.horizon_seconds, plan.time_step_seconds
    if not _count(horizon) or not _count(step) or not horizon or not step or horizon % step:
        raise ReviewUnavailable("invalid_timeline")
    if not isinstance(plan.timeline, list) or len(plan.timeline) != horizon // step + 1:
        raise ReviewUnavailable("invalid_timeline")
    population = plan.initial_population
    frames = []
    for index, raw in enumerate(plan.timeline):
        if (not isinstance(raw, dict) or type(raw.get("step")) is not int or raw["step"] != index
                or type(raw.get("time_seconds")) is not int or raw["time_seconds"] != index * step
                or not all(_count(raw.get(key)) for key in COUNT_FIELDS)):
            raise ReviewUnavailable("invalid_timeline")
        holding = sum(raw[key] for key in ZONE_FIELDS.values())
        if holding + raw["in_transit_occupancy"] + raw["total_completed"] != population:
            raise ReviewUnavailable("invalid_timeline")
        frames.append(MappingProxyType({key: raw[key] for key in ("step", "time_seconds", *COUNT_FIELDS)}))
    last = frames[-1]
    if (last["total_completed"] != plan.completed_crossings or last["in_transit_occupancy"]
            or any(last[key] != plan.zone_occupancy.get(zone, 0) for zone, key in ZONE_FIELDS.items())
            or any(last[key] != plan.boundary_breakdown.get(boundary, 0) for boundary, key in BOUNDARY_FIELDS.items())):
        raise ReviewUnavailable("invalid_timeline")
    return tuple(frames)


def available_portals(basis: ReviewBasis) -> frozenset:
    """Portals the accepted layout may use; the actuated reserve needs an observed OPEN endpoint."""
    return frozenset(portal_id for portal_id, spec in basis.venue.portals.items()
                     if portal_id not in basis.blocked_portals
                     and (not spec.is_actuated or basis.gate_state == GateObservedState.OPEN))


def reachable_zones(basis: ReviewBasis) -> frozenset:
    """Zones reachable from populated zones over available portals, from the venue spec alone."""
    reached = {zone_id for zone_id, spec in basis.venue.zones.items() if spec.initial_occupants > 0}
    usable = [basis.venue.portals[portal_id] for portal_id in available_portals(basis)]
    changed = True
    while changed:
        changed = False
        for spec in usable:
            if spec.from_zone in reached and spec.to_zone not in reached:
                reached.add(spec.to_zone)
                changed = True
    return frozenset(reached)


def boundary_quota(basis: ReviewBasis, boundary_id: str) -> int:
    # Same rule as the planner and checker: int(rate * horizon).
    return int(basis.venue.boundaries[boundary_id].service_rate_per_sec * basis.plan.horizon_seconds)


def boundary_step_limit(basis: ReviewBasis, boundary_id: str) -> int:
    # Same rule as the solver and schedule checker: a boundary always services at least one per step.
    return max(1, int(basis.venue.boundaries[boundary_id].service_rate_per_sec * basis.plan.time_step_seconds))
