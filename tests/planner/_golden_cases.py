"""Shared definition of the v1 planner golden cases (guard that v1 numbers never drift)."""
from backend.app.contracts import AlternativeId, RunContext
from backend.app.planner.flow_solver import FlowPlanner

CONTEXT = RunContext(geometry_revision="geom-shack15-v1", scenario_revision=1, physical_revision=1,
                     state_epoch="golden-epoch")
K, O = AlternativeId.KEEP_CURRENT, AlternativeId.OPEN_P3

CASES = {
    "baseline_keep": dict(alternative_id=K, blocked_portals=set(), blocked_boundaries=set()),
    "baseline_open_p3": dict(alternative_id=O, blocked_portals=set(), blocked_boundaries=set()),
    "p1_keep": dict(alternative_id=K, blocked_portals={"P1"}, blocked_boundaries=set()),
    "p1_open_p3": dict(alternative_id=O, blocked_portals={"P1"}, blocked_boundaries=set()),
    "p2_keep": dict(alternative_id=K, blocked_portals={"P2"}, blocked_boundaries=set()),
    "p2_open_p3": dict(alternative_id=O, blocked_portals={"P2"}, blocked_boundaries=set()),
    "b2_keep": dict(alternative_id=K, blocked_portals=set(), blocked_boundaries={"B2"}),
    "b2_open_p3": dict(alternative_id=O, blocked_portals=set(), blocked_boundaries={"B2"}),
    "smoke_p2_close12": dict(alternative_id=K, blocked_portals=set(), blocked_boundaries=set(),
                             portal_close_at={"P2": 12}),
    "smoke_b2_close12": dict(alternative_id=K, blocked_portals=set(), blocked_boundaries=set(),
                             boundary_close_at={"B2": 12}),
}


def run_case(name: str) -> dict:
    envelope = FlowPlanner().solve(CONTEXT, **CASES[name])
    data = envelope.model_dump(mode="json")
    data.pop("run_id", None)
    data.pop("timings_ms", None)
    return data
