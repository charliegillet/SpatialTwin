import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

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
    closed_from: dict[str, int] = {}
    for h in scenario.hazards:
        k0 = math.ceil(h.from_s / p.dt_s - 1e-9)
        closed_from[h.door_id] = min(k0, closed_from.get(h.door_id, k0))
    for d in graph.doors:
        flows = run.door_flows[d.id]
        assert len(flows) == K
        is_open = d.state == "open" or d.id in opened
        for k, f in enumerate(flows):
            if not is_open or k >= closed_from.get(d.id, K + 1):
                assert f == 0, (d.id, k, f)
            assert abs(f) <= door_capacity_at_step(d, k, p)
            if d.b == "OUTSIDE":
                assert f >= 0  # exits only carry flow outward (a -> b positive)
            if d.a == "OUTSIDE":
                assert f <= 0  # outward is b -> a, so negative


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


def test_intervention_opens_locked_door_plain_fixture(office_graph):
    base = solve(office_graph, Scenario(), FlowParams())
    opened = solve(office_graph, Scenario(interventions=["OPEN:D5"]), FlowParams())
    assert opened.reached_exit >= base.reached_exit
    _check_invariants(base, office_graph, Scenario())
    _check_invariants(opened, office_graph, Scenario(interventions=["OPEN:D5"]))


def test_reached_by_step_is_earliest_arrival(office_graph):
    s = Scenario(hazards=[Hazard(door_id="D2", kind="fire", from_s=0)],
                 interventions=["OPEN:D5"])
    p = FlowParams()
    K = p.horizon_s // p.dt_s
    run = solve(office_graph, s, p)
    for k in range(1, K + 1):
        sub = solve(office_graph, s, FlowParams(horizon_s=k * p.dt_s))
        assert run.reached_by_step[k] == sub.reached_exit, k
    last = next(k for k in range(K + 1) if run.reached_by_step[k] == run.reached_exit)
    print(f"\nfire D2 + OPEN:D5: all {run.reached_exit} reached by k={last}, "
          f"reached_by_step[40]={run.reached_by_step[40]}")
    _check_invariants(run, office_graph, s)


def _interior_doors(graph):
    return [d for d in graph.doors if "OUTSIDE" not in (d.a, d.b)]


def _assert_no_door_reversal(run, graph):
    # Through any interior door, flow runs one way only over the whole run:
    # nobody walks into a zone and back out through the same door.
    for d in _interior_doors(graph):
        flows = run.door_flows[d.id]
        assert not (any(f > 0 for f in flows) and any(f < 0 for f in flows)), (d.id, flows)


def test_no_dead_end_detours(office_graph):
    s = Scenario(hazards=[Hazard(door_id="D2", kind="fire", from_s=0)],
                 interventions=["OPEN:D5"])
    run = solve(office_graph, s, FlowParams(horizon_s=120))
    assert all(f == 0 for f in run.door_flows["D1"])  # Z2's only exit is on fire
    assert all(f >= 0 for f in run.door_flows["D6"])  # Z4 only empties
    assert sum(run.door_flows["D6"]) == 10
    _assert_no_door_reversal(run, office_graph)
    _check_invariants(run, office_graph, s)
    for s2 in [Scenario(), Scenario(interventions=["OPEN:D5"]),
               Scenario(hazards=[Hazard(door_id="D4", kind="fire", from_s=30)])]:
        for horizon in (20, 60, 120):
            r = solve(office_graph, s2, FlowParams(horizon_s=horizon))
            _assert_no_door_reversal(r, office_graph)
            assert all(f >= 0 for f in r.door_flows["D6"])


def test_exit_written_outside_first():
    # Exit stored as a=OUTSIDE, b=Z1: outward flow is b->a, so negative.
    g = _graph(
        [_zone("Z1", (0, 0, 10, 10), 50)],
        [_door("D1", "OUTSIDE", "Z1", 1.0, 1.0, (10, 5))],
    )
    run = solve(g, Scenario(), FlowParams(horizon_s=20))
    assert run.reached_exit == 14
    assert sum(run.door_flows["D1"]) == -14 and max(run.door_flows["D1"]) <= 0
    _check_invariants(run, g, Scenario())


def test_unknown_ids_raise(office_graph):
    with pytest.raises(ValueError):
        solve(office_graph, Scenario(hazards=[Hazard(door_id="D99", kind="fire")]),
              FlowParams())
    with pytest.raises(ValueError):
        solve(office_graph, Scenario(interventions=["OPEN:D99"]), FlowParams())
    doors = [d.model_copy(update={"b": "Z9"}) if d.id == "D1" else d
             for d in office_graph.doors]
    with pytest.raises(ValueError):
        solve(office_graph.model_copy(update={"doors": doors}), Scenario(), FlowParams())


_SEED_SCRIPT = """
import json, sys
from pathlib import Path
from walktwin.contracts import FlowParams, Hazard, Scenario, VenueGraph
from walktwin.flow import solve
g = VenueGraph.model_validate_json(Path(sys.argv[1]).read_text())
out = []
for s in [Scenario(), Scenario(interventions=["OPEN:D5"]),
          Scenario(hazards=[Hazard(door_id="D2", kind="fire", from_s=0)],
                   interventions=["OPEN:D5"]),
          Scenario(hazards=[Hazard(door_id="D4", kind="fire", from_s=30)])]:
    for h in (20, 60, 120):
        r = solve(g, s, FlowParams(horizon_s=h))
        out.append([r.run_id, r.door_flows, r.reached_by_step, r.zone_occupancy])
print(json.dumps(out, sort_keys=True))
"""


def test_deterministic_across_hash_seeds():
    root = Path(__file__).resolve().parents[1]
    fixture = root / "tests" / "fixtures" / "office_graph.json"
    results = {}
    for seed in ("0", "1", "9", "18", "35"):
        env = {**os.environ, "PYTHONHASHSEED": seed,
               "PYTHONPATH": str(root / "backend")}
        proc = subprocess.run(
            [sys.executable, "-c", _SEED_SCRIPT, str(fixture)],
            env=env, capture_output=True, text=True, check=True, cwd=root,
        )
        results[seed] = json.loads(proc.stdout)
    first = results["0"]
    for seed, res in results.items():
        assert res == first, f"PYTHONHASHSEED={seed} differs"


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
