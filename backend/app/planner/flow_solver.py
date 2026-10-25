"""
Deterministic Finite-Horizon Network Flow Planner
Implements all-population two-phase min-cost flow to rigorously account for
every occupant without heuristic shortcuts or fabricated survival metrics.
"""

from __future__ import annotations
import hashlib
import time
from uuid import uuid4
from typing import Dict, List, Optional, Set, Tuple
import networkx as nx

from backend.app.contracts import (
    AlternativeId,
    ComputationStatus,
    EvaluationEnvelope,
    RunContext,
)
from backend.app.planner.checker import PlanChecker
from backend.app.planner.model import VenueGraph, get_default_venue_graph


class FlowPlanner:
    def __init__(self, venue_graph: Optional[VenueGraph] = None):
        self.venue = venue_graph or get_default_venue_graph()
        self.checker = PlanChecker(self.venue)

    @staticmethod
    def _validate_closures(close_at, elements, kind, H, dt) -> Dict[str, int]:
        if not close_at:
            return {}
        out: Dict[str, int] = {}
        for element_id, when in close_at.items():
            if element_id not in elements:
                raise ValueError(f"Unknown {kind} id in closure schedule: {element_id!r}")
            if type(when) is not int or when < 0 or when % dt or when > H:
                raise ValueError(
                    f"Closure time for {kind} {element_id} must be a non-negative multiple of {dt}s within {H}s"
                )
            out[element_id] = when
        return out

    def solve(
        self,
        base_context: RunContext,
        alternative_id: AlternativeId,
        blocked_portals: Set[str],
        blocked_boundaries: Set[str],
        p3_physical_open: bool = False,
        horizon_seconds: Optional[int] = None,
        time_step_seconds: Optional[int] = None,
        portal_close_at: Optional[Dict[str, int]] = None,
        boundary_close_at: Optional[Dict[str, int]] = None,
    ) -> EvaluationEnvelope:
        start_time = time.perf_counter()

        H = horizon_seconds or self.venue.default_horizon_seconds
        dt = time_step_seconds or self.venue.time_step_seconds
        T = H // dt  # Number of time steps

        # Forecast-closure model: closure times are known in advance and a closed
        # element keeps its edges only for time indices t < close_at // dt.
        portal_close = self._validate_closures(portal_close_at, self.venue.portals, "portal", H, dt)
        boundary_close = self._validate_closures(boundary_close_at, self.venue.boundaries, "boundary", H, dt)

        # Determine effective P3 state based on alternative
        p3_effective_open = (alternative_id == AlternativeId.OPEN_P3) or (
            alternative_id == AlternativeId.KEEP_CURRENT and p3_physical_open
        )

        effective_blocked_portals = set(blocked_portals)
        if not p3_effective_open:
            effective_blocked_portals.add("P3")
        elif "P3" in effective_blocked_portals:
            effective_blocked_portals.remove("P3")

        effective_blocked_boundaries = set(blocked_boundaries)

        # Initial population
        N = self.venue.zones["EVENT"].initial_occupants

        # Candidate hash differs deterministically by scenario and alternative
        candidate_seed = (
            f"{base_context.compute_hash()}:{alternative_id.value}:"
            f"portals={sorted(effective_blocked_portals)}:boundaries={sorted(effective_blocked_boundaries)}:H={H}:dt={dt}"
        )
        if portal_close or boundary_close:
            candidate_seed += (
                f":portal_close={sorted(portal_close.items())}"
                f":boundary_close={sorted(boundary_close.items())}"
            )
        candidate_hash = hashlib.sha256(candidate_seed.encode("utf-8")).hexdigest()[:16]
        run_id = f"run-{uuid4().hex}"

        # Build Time-Expanded Flow Network
        G = nx.DiGraph()

        SOURCE = "SOURCE"
        EXIT_COLLECTOR = "EXIT_COLLECTOR"
        UNASSIGNED_COLLECTOR = "UNASSIGNED_COLLECTOR"

        # 1. Source injection
        G.add_edge(SOURCE, ("EVENT", 0), capacity=N, weight=0)

        # 2. Zone waiting arcs across time
        for z_id, z_spec in self.venue.zones.items():
            cap = z_spec.max_capacity
            for t in range(T):
                # Wait arc: cost 1 to encourage progress
                G.add_edge((z_id, t), (z_id, t + 1), capacity=cap, weight=1)

        # 3. Portal transitions
        for p_id, p_spec in self.venue.portals.items():
            if p_id in effective_blocked_portals:
                continue

            u, v = p_spec.from_zone, p_spec.to_zone
            steps = max(1, p_spec.travel_time_seconds // dt)
            slot_capacity = max(1, int(p_spec.throughput_per_sec * dt))

            last_departure = T - steps + 1
            if p_id in portal_close:
                last_departure = min(last_departure, portal_close[p_id] // dt)
            for t in range(last_departure):
                G.add_edge((u, t), (v, t + steps), capacity=slot_capacity, weight=2)

        # 4. Boundary floor-transfer crossings
        boundary_edges_by_id: Dict[str, List[Tuple[Any, Any]]] = {}
        for b_id, b_spec in self.venue.boundaries.items():
            boundary_edges_by_id[b_id] = []
            if b_id in effective_blocked_boundaries:
                continue

            u = b_spec.from_zone
            slot_capacity = max(1, int(b_spec.service_rate_per_sec * dt))

            last_service = T + 1
            if b_id in boundary_close:
                last_service = min(last_service, boundary_close[b_id] // dt)
            for t in range(last_service):
                edge = ((u, t), f"B_{b_id}_{t}")
                G.add_edge((u, t), f"B_{b_id}_{t}", capacity=slot_capacity, weight=0)
                G.add_edge(f"B_{b_id}_{t}", EXIT_COLLECTOR, capacity=slot_capacity, weight=0)
                boundary_edges_by_id[b_id].append(edge)

        # 5. Horizon unassigned collector from all zones at time T
        for z_id, z_spec in self.venue.zones.items():
            G.add_edge((z_id, T), UNASSIGNED_COLLECTOR, capacity=z_spec.max_capacity, weight=0)

        # -------------------------------------------------------------
        # PHASE 1: Maximize completed boundary crossings
        # -------------------------------------------------------------
        SINK = "SINK"
        G.add_edge(EXIT_COLLECTOR, SINK, capacity=N, weight=-1000)
        G.add_edge(UNASSIGNED_COLLECTOR, SINK, capacity=N, weight=0)

        G.nodes[SOURCE]["demand"] = -N
        G.nodes[SINK]["demand"] = N

        try:
            flow_dict = nx.min_cost_flow(G)
            completed_crossings = flow_dict[EXIT_COLLECTOR][SINK]
        except nx.NetworkXUnfeasible:
            # If completely unfeasible (e.g. storage overflow)
            completed_crossings = 0

        # Remove temporary SINK for Phase 2
        G.remove_node(SINK)

        # -------------------------------------------------------------
        # PHASE 2: Optimize schedule at exact maximum exit count
        # -------------------------------------------------------------
        remaining_population = N - completed_crossings

        G.nodes[SOURCE]["demand"] = -N
        G.nodes[EXIT_COLLECTOR]["demand"] = completed_crossings
        G.nodes[UNASSIGNED_COLLECTOR]["demand"] = remaining_population

        try:
            flow_dict = nx.min_cost_flow(G)
        except nx.NetworkXUnfeasible:
            # Fallback
            flow_dict = {}

        # -------------------------------------------------------------
        # Accounting & Breakdown
        # -------------------------------------------------------------
        boundary_breakdown: Dict[str, int] = {b_id: 0 for b_id in self.venue.boundaries}
        for b_id, edges in boundary_edges_by_id.items():
            total_b_flow = 0
            for u, mid in edges:
                total_b_flow += flow_dict.get(u, {}).get(mid, 0)
            boundary_breakdown[b_id] = total_b_flow

        # Zone residual occupancy at time T
        zone_occupancy: Dict[str, int] = {}
        for z_id in self.venue.zones:
            zone_occupancy[z_id] = flow_dict.get((z_id, T), {}).get(UNASSIGNED_COLLECTOR, 0)

        # Build dynamic time-series schedule (timeline)
        timeline: List[Dict[str, Any]] = []
        cum_b1 = 0
        cum_b2 = 0
        for t in range(T + 1):
            time_sec = t * dt
            step_b1 = 0
            step_b2 = 0
            if "B1" in boundary_edges_by_id:
                for u, mid in boundary_edges_by_id["B1"]:
                    if u == ("WEST", t):
                        step_b1 += flow_dict.get(u, {}).get(mid, 0)
            if "B2" in boundary_edges_by_id:
                for u, mid in boundary_edges_by_id["B2"]:
                    if u == ("EAST", t):
                        step_b2 += flow_dict.get(u, {}).get(mid, 0)

            cum_b1 += step_b1
            cum_b2 += step_b2

            # Snapshot after arrivals and boundary service, before departures.
            # Departing people remain in their origin at this sample; longer
            # journeys have an explicit in-transit count between sample times.
            step_occ: Dict[str, int] = {}
            for z_id in self.venue.zones:
                node = (z_id, t)
                incoming = sum(edges.get(node, 0) for edges in flow_dict.values())
                boundary_service = sum(amount for destination, amount in flow_dict.get(node, {}).items()
                                       if isinstance(destination, str) and destination.startswith("B_"))
                step_occ[z_id] = incoming - boundary_service
            in_transit = 0
            for source, destinations in flow_dict.items():
                if not isinstance(source, tuple):
                    continue
                for destination, amount in destinations.items():
                    if isinstance(destination, tuple) and source[0] != destination[0] and source[1] < t < destination[1]:
                        in_transit += amount

            timeline.append({
                "step": t,
                "time_seconds": time_sec,
                "event_occupancy": step_occ.get("EVENT", 0),
                "west_occupancy": step_occ.get("WEST", 0),
                "east_occupancy": step_occ.get("EAST", 0),
                "reserve_occupancy": step_occ.get("RESERVE", 0),
                "in_transit_occupancy": in_transit,
                "b1_cumulative": cum_b1,
                "b2_cumulative": cum_b2,
                "total_completed": cum_b1 + cum_b2,
            })

        # Identify bottlenecks
        bottlenecks = []
        for b_id, b_spec in self.venue.boundaries.items():
            max_b_quota = int(b_spec.service_rate_per_sec * H)
            if boundary_breakdown.get(b_id, 0) >= max_b_quota - 2 and max_b_quota > 0:
                bottlenecks.append(f"Boundary {b_id} reached 100% capacity quota ({max_b_quota} pers)")

        for p_id in ("P1", "P2", "P3"):
            if p_id in effective_blocked_portals:
                bottlenecks.append(f"Portal {p_id} BLOCKED")

        # Status determination
        if completed_crossings == N:
            status = ComputationStatus.COMPLETE_WITHIN_MODEL
        elif completed_crossings > 0:
            status = ComputationStatus.PARTIAL_WITHIN_HORIZON
        else:
            status = ComputationStatus.NO_FEASIBLE_EXIT

        # Assumptions
        assumptions = [
            f"Horizon: {H}s, step: {dt}s, initial synthetic population: {N}",
            "Single-commodity all-population network flow with full occupant conservation",
            "Finite-rate floor transfer boundaries: " + ", ".join(
                f"{key} ({spec.service_rate_per_sec:g} people/s)" for key, spec in self.venue.boundaries.items()),
            "P3 operates as miniature internal reserve connector feeding existing B2",
        ]

        # Independent Validation
        validator_report = self.checker.validate(
            base_context=base_context,
            blocked_portals=effective_blocked_portals,
            blocked_boundaries=effective_blocked_boundaries,
            p3_is_open=p3_effective_open,
            initial_population=N,
            completed_crossings=completed_crossings,
            remaining_population=remaining_population,
            boundary_breakdown=boundary_breakdown,
            zone_occupancy=zone_occupancy,
            status=status,
            horizon_seconds=H,
            time_step_seconds=dt,
            timeline=timeline,
            flow_witness=flow_dict,
            portal_close_at=portal_close or None,
            boundary_close_at=boundary_close or None,
        )

        timings_ms = (time.perf_counter() - start_time) * 1000.0

        return EvaluationEnvelope(
            run_id=run_id,
            base_context=base_context,
            candidate_hash=candidate_hash,
            alternative_id=alternative_id,
            status=status,
            initial_population=N,
            completed_crossings=completed_crossings,
            remaining_population=remaining_population,
            horizon_seconds=H,
            time_step_seconds=dt,
            boundary_breakdown=boundary_breakdown,
            zone_occupancy=zone_occupancy,
            timeline=timeline,
            bottlenecks=bottlenecks,
            assumptions=assumptions,
            validator_report=validator_report,
            timings_ms=round(timings_ms, 2),
            provenance="fixed_numerical_flow_solver_v1",
        )
