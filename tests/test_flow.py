import time

import pytest

from walktwin.contracts import (
    Door,
    Evidence,
    FlowParams,
    Hazard,
    Measure,
    Scenario,
    VenueGraph,
    Zone,
)
from walktwin.flow import (
    FlowRun,
    door_capacity_at_step,
    door_rate_per_step,
    solve,
    travel_steps,
)

EV = [Evidence(start_s=0, end_s=1, note="n")]


def _zone(zid: str, rect, occupants: int) -> Zone:
    return Zone(id=zid, name=zid, rect=rect, occupants=occupants, evidence=EV)


def _door(did, a, b, low, high, pos, kind="exit", state="open") -> Door:
    return Door(
        id=did, a=a, b=b, kind=kind, state=state,
        clear_width=Measure(low_m=low, high_m=high, basis="estimated"),
        position=pos, evidence=EV,
    )


def _graph(zones, doors) -> VenueGraph:
    return VenueGraph(
        schema_version="1", video_sha256="t", anchor=None,
        zones=zones, doors=doors, keyframes=[],
    )


def _single_room(low=1.0, high=1.0) -> VenueGraph:
    # 10x10 room, centroid (5,5); exit at the east edge, 5 m from the centroid.
    return _graph(
        [_zone("Z1", (0, 0, 10, 10), 50)],
        [_door("D1", "Z1", "OUTSIDE", low, high, (10, 5))],
    )


def _check_invariants(run: FlowRun, graph: VenueGraph, scenario: Scenario) -> None:
    p = run.params
    K = p.horizon_s // p.dt_s
    assert len(run.zone_occupancy) == K + 1
    assert len(run.transit_by_step) == K + 1
    assert len(run.reached_by_step) == K + 1
    for k in range(K + 1):
        occ = run.zone_occupancy[k]
        assert all(v >= 0 for v in occ.values())
        assert sum(occ.values()) + run.transit_by_step[k] + run.reached_by_step[k] == run.total
    assert run.zone_occupancy[0] == {z.id: z.occupants for z in graph.zones}
    assert run.reached_by_step[0] == 0
    assert all(a <= b for a, b in zip(run.reached_by_step, run.reached_by_step[1:]))
    assert run.reached_by_step[K] == run.reached_exit
    assert run.remaining_by_zone == run.zone_occupancy[K]
    assert run.in_transit_end == run.transit_by_step[K]
    assert run.reached_exit + sum(run.remaining_by_zone.values()) + run.in_transit_end == run.total
    opened = {i.split(":", 1)[1] for i in scenario.interventions if i.startswith("OPEN:")}
    for d in graph.doors:
        flows = run.door_flows[d.id]
        assert len(flows) == K
        is_open = d.state == "open" or d.id in opened
        for k, f in enumerate(flows):
            if not is_open:
                assert f == 0
            assert abs(f) <= door_capacity_at_step(d, k, p)
            if d.b == "OUTSIDE":
                assert f >= 0  # exits only carry flow outward


def test_single_room_single_exit():
    g = _single_room()
    p = FlowParams()
    d = g.doors[0]
    assert door_rate_per_step(d, p) == pytest.approx(1.82)
    assert travel_steps(g, d, "Z1", "OUTSIDE", p) == 3

    run = solve(g, Scenario(), FlowParams(horizon_s=120))
    assert run.total == 50
    assert run.reached_exit == 50
    _check_invariants(run, g, Scenario())

    short = solve(g, Scenario(), FlowParams(horizon_s=20))  # K = 10
    assert short.reached_exit == 14  # floor(8 * 1.82)
    assert short.remaining_by_zone == {"Z1": 36}
    assert short.in_transit_end == 0
    flows = short.door_flows["D1"]
    assert sum(flows[:8]) == 14 and flows[8:] == [0, 0]
    _check_invariants(short, g, Scenario())


def test_cumulative_rounding():
    # low 1.4 -> effective 1.1 -> c = 1.3 * 1.1 * 1 = 1.43 at dt_s = 1
    d = _door("D1", "Z1", "OUTSIDE", 1.4, 1.4, (0, 0))
    p = FlowParams(dt_s=1)
    assert door_rate_per_step(d, p) == pytest.approx(1.43)
    assert sum(door_capacity_at_step(d, k, p) for k in range(10)) == 14


def test_cumulative_rounding_is_float_robust():
    # c = 1.3 * 0.7 * 2 evaluates to 1.8199999999999998 in floats; 50 * c must
    # still floor to 91 and 100 * c to 182.
    d = _door("D1", "Z1", "OUTSIDE", 1.0, 1.0, (0, 0))
    p = FlowParams()
    assert sum(door_capacity_at_step(d, k, p) for k in range(8)) == 14
    assert sum(door_capacity_at_step(d, k, p) for k in range(50)) == 91
    assert sum(door_capacity_at_step(d, k, p) for k in range(100)) == 182
    assert all(door_capacity_at_step(d, k, p) in (1, 2) for k in range(100))


def test_narrow_door_effective_width_zero():
    g = _single_room(0.28, 0.30)
    p = FlowParams()
    assert door_rate_per_step(g.doors[0], p) == 0
    run = solve(g, Scenario(), p)
    assert run.reached_exit == 0
    assert run.remaining_by_zone == {"Z1": 50}
    _check_invariants(run, g, Scenario())


def test_hazard_closes_exit():
    g = _single_room()
    s = Scenario(hazards=[Hazard(door_id="D1", kind="fire", from_s=0)])
    run = solve(g, s, FlowParams())
    assert run.reached_exit == 0
    assert run.remaining_by_zone == {"Z1": 50}
    assert run.door_flows["D1"] == [0] * 60
    _check_invariants(run, g, s)


def test_hazard_from_mid_run_closes_later_steps():
    g = _single_room()
    s = Scenario(hazards=[Hazard(door_id="D1", kind="fire", from_s=9)])  # ceil(4.5) = 5
    run = solve(g, s, FlowParams())
    assert all(f == 0 for f in run.door_flows["D1"][5:])
    assert run.reached_exit == 9  # floor(5 * 1.82)
    _check_invariants(run, g, s)


def test_intervention_opens_locked_door(office_graph):
    # Fire on the west exit D2 from 0 s removes the west route, so the east
    # exit D4 (0.9 m) is a bottleneck; opening the locked D5 must help.
    fire = [Hazard(door_id="D2", kind="fire", from_s=0)]
    base_s = Scenario(hazards=fire)
    open_s = Scenario(hazards=fire, interventions=["OPEN:D5"])
    base = solve(office_graph, base_s, FlowParams())
    opened = solve(office_graph, open_s, FlowParams())
    print(f"\nreached_exit locked D5={base.reached_exit} OPEN:D5={opened.reached_exit}")
    assert opened.reached_exit >= base.reached_exit
    assert opened.reached_exit > base.reached_exit  # strict for this scenario
    assert all(f == 0 for f in base.door_flows["D5"])
    assert sum(opened.door_flows["D5"]) > 0
    _check_invariants(base, office_graph, base_s)
    _check_invariants(opened, office_graph, open_s)


def test_unreachable_zone_counts_as_remaining(office_graph):
    doors = [d.model_copy(update={"state": "locked"}) if d.id == "D6" else d
             for d in office_graph.doors]
    g = office_graph.model_copy(update={"doors": doors})
    run = solve(g, Scenario(), FlowParams())
    assert run.remaining_by_zone["Z4"] == 10
    assert all(f == 0 for f in run.door_flows["D6"])
    _check_invariants(run, g, Scenario())


def test_conservation_every_step(office_graph):
    for s in [
        Scenario(),
        Scenario(interventions=["OPEN:D5"]),
        Scenario(hazards=[Hazard(door_id="D2", kind="fire", from_s=0)]),
        Scenario(hazards=[Hazard(door_id="D4", kind="fire", from_s=30)]),
    ]:
        for horizon in (20, 60, 120):
            run = solve(office_graph, s, FlowParams(horizon_s=horizon))
            K = horizon // 2
            for k in range(K + 1):
                assert (sum(run.zone_occupancy[k].values()) + run.transit_by_step[k]
                        + run.reached_by_step[k]) == run.total == 130
            _check_invariants(run, office_graph, s)


def test_door_flow_sign_convention(office_graph):
    run = solve(office_graph, Scenario(), FlowParams())
    # D1 a=Z1 b=Z2: people move Z1 -> Z2 (positive).
    assert sum(run.door_flows["D1"]) > 0 and min(run.door_flows["D1"]) >= 0
    # D6 a=Z4 b=Z1: people move Z4 -> Z1 (positive).
    assert sum(run.door_flows["D6"]) == 10
    # Reverse D1's orientation (a=Z2, b=Z1): the same movement is negative.
    doors = [d.model_copy(update={"a": "Z2", "b": "Z1"}) if d.id == "D1" else d
             for d in office_graph.doors]
    g = office_graph.model_copy(update={"doors": doors})
    rev = solve(g, Scenario(), FlowParams())
    assert sum(rev.door_flows["D1"]) < 0 and max(rev.door_flows["D1"]) <= 0
    assert rev.reached_exit == run.reached_exit
    _check_invariants(run, office_graph, Scenario())
    _check_invariants(rev, g, Scenario())


def test_travel_steps_fixture(office_graph):
    p = FlowParams()
    doors = {d.id: d for d in office_graph.doors}
    # Z1 centroid (9,4) -> D1 (3,4) 6 m -> Z2 centroid (1.5,4) 1.5 m: 7.5/1.2/2 = 3.125
    assert travel_steps(office_graph, doors["D1"], "Z1", "Z2", p) == 4
    assert travel_steps(office_graph, doors["D1"], "Z2", "Z1", p) == 4
    # Z2 centroid (1.5,4) -> D2 (0,4) 1.5 m: 0.625 -> max(1, 1)
    assert travel_steps(office_graph, doors["D2"], "Z2", "OUTSIDE", p) == 1


def test_deterministic_run_id(office_graph):
    p = FlowParams()
    s = Scenario(interventions=["OPEN:D5"])
    a = solve(office_graph, s, p)
    b = solve(office_graph, s, p)
    assert a.run_id == b.run_id
    assert a.run_id.startswith("r-") and len(a.run_id) == 14
    assert a.door_flows == b.door_flows
    assert a.zone_occupancy == b.zone_occupancy
    assert a.graph_revision == office_graph.revision
    assert a.scenario_hash == s.hash
    assert solve(office_graph, Scenario(), p).run_id != a.run_id
    assert solve(office_graph, s, FlowParams(horizon_s=60)).run_id != a.run_id


def test_solve_speed(office_graph):
    p = FlowParams(horizon_s=120)
    t0 = time.perf_counter()
    run = solve(office_graph, Scenario(interventions=["OPEN:D5"]), p)
    elapsed = time.perf_counter() - t0
    print(f"\nsolve(office fixture, horizon_s=120): {elapsed * 1000:.1f} ms, "
          f"reached_exit={run.reached_exit}/{run.total}")
    assert elapsed < 1.0
