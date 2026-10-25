"""
Independent Numerical Validator & Checker for SpatialTwin
Ensures every occupant is accounted for, capacities are respected,
and no blocked paths or unachieved claims pass through to publication.
"""

from typing import Dict, List, Set, Tuple, Optional, Any
from backend.app.planner.schedule_checker import validate_schedule
from backend.app.contracts import (
    ComputationStatus,
    EvaluationEnvelope,
    RunContext,
    ValidatorReport,
)
from backend.app.planner.model import VenueGraph


class PlanChecker:
    """
    Independent checker that inspects a solved candidate plan against
    the canonical venue graph, active blockage set, and initial population.
    """

    def __init__(self, venue_graph: VenueGraph):
        self.venue = venue_graph

    def validate(
        self,
        base_context: RunContext,
        blocked_portals: Set[str],
        blocked_boundaries: Set[str],
        p3_is_open: bool,
        initial_population: int,
        completed_crossings: int,
        remaining_population: int,
        boundary_breakdown: Dict[str, int],
        zone_occupancy: Dict[str, int],
        status: ComputationStatus,
        horizon_seconds: int,
        time_step_seconds: int,
        timeline: Optional[List[Dict[str, Any]]] = None,
        flow_witness: Optional[Dict[Any, Dict[Any, int]]] = None,
        portal_close_at: Optional[Dict[str, int]] = None,
        boundary_close_at: Optional[Dict[str, int]] = None,
    ) -> ValidatorReport:
        checks_run = []
        reasons = []

        # 1. Total Population Conservation Check
        checks_run.append("population_conservation")
        conservation_verified = (initial_population == completed_crossings + remaining_population)
        if not conservation_verified:
            reasons.append(
                f"Conservation violated: initial ({initial_population}) != "
                f"completed ({completed_crossings}) + remaining ({remaining_population})"
            )

        # 2. Boundary Breakdown Sum Check
        checks_run.append("boundary_sum_consistency")
        sum_boundaries = sum(boundary_breakdown.values())
        if sum_boundaries != completed_crossings:
            reasons.append(
                f"Boundary crossings sum ({sum_boundaries}) != completed crossings ({completed_crossings})"
            )

        # 3. Blocked Boundary Crossings Check
        checks_run.append("blocked_boundaries_zero_flow")
        for b_id in blocked_boundaries:
            if boundary_breakdown.get(b_id, 0) > 0:
                reasons.append(f"Blocked boundary {b_id} serviced {boundary_breakdown[b_id]} occupants; must be 0")

        # 4. P3 State and Flow Consistency
        checks_run.append("p3_gate_admissibility")
        p3_closed = (not p3_is_open) or "P3" in blocked_portals
        if p3_closed:
            # RESERVE is reachable only through P3, so a closed P3 means no EVENT->RESERVE flow
            # in the witness and no reserve occupancy in any timeline frame.
            p3_flow = sum(
                amount
                for source, destinations in (flow_witness or {}).items()
                if isinstance(source, tuple) and source[0] == "EVENT"
                for destination, amount in destinations.items()
                if isinstance(destination, tuple) and destination[0] == "RESERVE" and amount
            )
            if p3_flow:
                reasons.append(f"P3 is closed but {p3_flow} occupants were routed through it; must be 0")
            if any(isinstance(f, dict) and f.get("reserve_occupancy") for f in (timeline or [])):
                reasons.append("P3 is closed but the timeline shows reserve occupancy; must be 0")

        # 5. Boundary Capacity / Rate Quota Check
        checks_run.append("boundary_quota_limits")
        quota_respected = True
        for b_id, b_spec in self.venue.boundaries.items():
            if b_id in blocked_boundaries:
                continue
            max_possible_crossings = int(b_spec.service_rate_per_sec * horizon_seconds)
            actual_crossings = boundary_breakdown.get(b_id, 0)
            if actual_crossings > max_possible_crossings:
                reasons.append(
                    f"Boundary {b_id} serviced {actual_crossings} exceeding max horizon quota {max_possible_crossings}"
                )
                quota_respected = False

        # 6. Unassigned / Residual Occupants Accounted Check
        checks_run.append("residual_occupant_accounting")
        sum_zone_remaining = sum(zone_occupancy.values())
        unassigned_accounted = (sum_zone_remaining == remaining_population)
        if not unassigned_accounted:
            reasons.append(
                f"Zone residual sum ({sum_zone_remaining}) != reported remaining population ({remaining_population})"
            )

        # 7. Zone Capacity Check
        checks_run.append("zone_storage_capacities")
        capacities_respected = True
        for z_id, count in zone_occupancy.items():
            z_spec = self.venue.zones.get(z_id)
            if z_spec and count > z_spec.max_capacity:
                reasons.append(f"Zone {z_id} residual {count} exceeds max capacity {z_spec.max_capacity}")
                capacities_respected = False

        # 8. Status Consistency Check
        checks_run.append("computation_status_consistency")
        if status in (ComputationStatus.SOLVER_INFEASIBLE, ComputationStatus.INVALID_INPUT,
                      ComputationStatus.SOLVER_TIMEOUT, ComputationStatus.STALE):
            reasons.append(f"Solver did not produce a feasible plan (status {status.value})")
        elif completed_crossings == initial_population and status != ComputationStatus.COMPLETE_WITHIN_MODEL:
            reasons.append(f"All occupants completed but status is {status}; expected COMPLETE_WITHIN_MODEL")
        elif 0 < completed_crossings < initial_population and status != ComputationStatus.PARTIAL_WITHIN_HORIZON:
            reasons.append(f"Partial completion ({completed_crossings}/{initial_population}) but status is {status}")
        elif completed_crossings == 0 and status != ComputationStatus.NO_FEASIBLE_EXIT:
            reasons.append(f"0 completed crossings but status is {status}; expected NO_FEASIBLE_EXIT")

        if timeline is not None:
            schedule_checks, schedule_reasons = validate_schedule(
                self.venue, timeline, initial_population, completed_crossings,
                zone_occupancy, boundary_breakdown, horizon_seconds, time_step_seconds,
                blocked_portals | ({"P3"} if not p3_is_open else set()), blocked_boundaries, flow_witness,
                portal_close_at, boundary_close_at,
            )
            checks_run.extend(schedule_checks)
            reasons.extend(schedule_reasons)

        is_valid = (
            conservation_verified
            and quota_respected
            and unassigned_accounted
            and capacities_respected
            and len(reasons) == 0
        )

        return ValidatorReport(
            is_valid=is_valid,
            checks_run=checks_run,
            reasons=reasons,
            conservation_verified=conservation_verified,
            unassigned_accounted=unassigned_accounted,
            capacities_respected=capacities_respected,
            quota_respected=quota_respected,
        )
