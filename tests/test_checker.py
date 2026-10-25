import math

from walktwin.checker import CheckResult, check_run
from walktwin.contracts import (
    Door, Evidence, FlowParams, Hazard, Measure, Scenario, VenueGraph, Zone,
)
from walktwin.flow import solve

EV = [Evidence(start_s=0, end_s=1, note="n")]
P = FlowParams()


def _zone(zid, rect, occ):
    return Zone(id=zid, name=zid, rect=rect, occupants=occ, evidence=EV)


def _door(did, a, b, low, pos, kind="exit", state="open"):
    return Door(id=did, a=a, b=b, kind=kind, state=state,
                clear_width=Measure(low_m=low, high_m=low, basis="estimated"),
                position=pos, evidence=EV)


def _graph(low=1.0):
    return VenueGraph(
        schema_version="1", video_sha256="t", anchor=None,
        zones=[_zone("Z1", (0, 0, 10, 10), 30), _zone("Z2", (10, 0, 10, 10), 20)],
        doors=[_door("D1", "Z1", "OUTSIDE", low, (0, 5)),
               _door("D2", "Z1", "Z2", 1.2, (10, 5), kind="door"),
               _door("D3", "Z2", "OUTSIDE", 1.0, (20, 5))],
        keyframes=[])


def _honest():
    g, s = _graph(), Scenario()
    return g, s, solve(g, s, P)


def _mut(run, **kw):
    return run.model_copy(update=kw)


def test_honest_run_passes():
    g, s, run = _honest()
    r = check_run(g, s, P, run)
    assert isinstance(r, CheckResult)
    assert r.ok, r.violations
    assert r.run_id == run.run_id


def test_inflated_door_flow_fails():
    g, s, run = _honest()
    flows = {k: list(v) for k, v in run.door_flows.items()}
    flows["D1"][3] += 5
    r = check_run(g, s, P, _mut(run, door_flows=flows))
    assert not r.ok
    assert any("D1" in m and "capacity" in m for m in r.violations)


def test_flow_through_hazard_fails():
    g = _graph()
    s = Scenario(hazards=[Hazard(door_id="D1", kind="fire", from_s=10)])
    run = solve(g, s, P)
    assert check_run(g, s, P, run).ok
    flows = {k: list(v) for k, v in run.door_flows.items()}
    flows["D1"][10] = 1
    r = check_run(g, s, P, _mut(run, door_flows=flows))
    assert not r.ok
    assert any("D1" in m and "closed" in m for m in r.violations)


def test_inflated_total_fails():
    g, s, run = _honest()
    r = check_run(g, s, P, _mut(run, reached_exit=run.reached_exit + 1))
    assert not r.ok
    assert any("total" in m for m in r.violations)


def test_stale_revision_fails():
    g, s, run = _honest()
    r = check_run(_graph(low=0.9), s, P, run)
    assert not r.ok
    assert any("revision" in m for m in r.violations)


def test_suboptimal_flow_still_valid():
    # One exit, plain per-step floors: lower than the cumulative rule, still legal.
    g = VenueGraph(schema_version="1", video_sha256="t", anchor=None,
                   zones=[_zone("Z1", (0, 0, 10, 10), 200)],
                   doors=[_door("D1", "Z1", "OUTSIDE", 1.0, (10, 5))], keyframes=[])
    s = Scenario()
    K = P.horizon_s // P.dt_s
    base = solve(g, s, P)
    d0 = next(k for k, f in enumerate(base.door_flows['D1']) if f)
    t = next(k for k, r in enumerate(base.reached_by_step) if r) - d0
    cap = math.floor(P.specific_flow_p_per_m_s * (1.0 - 0.3) * P.dt_s)
    flows = [cap if k + t <= K else 0 for k in range(K)]
    occ, transit, reached = [], [], []
    for k in range(K + 1):
        occ.append({"Z1": 200 - sum(flows[:k])})
        transit.append(sum(f for j, f in enumerate(flows[:k]) if j + t > k))
        reached.append(sum(f for j, f in enumerate(flows) if j + t <= k))
    assert sum(flows) < base.reached_exit
    run = base.model_copy(update=dict(
        door_flows={"D1": flows}, zone_occupancy=occ, transit_by_step=transit,
        reached_by_step=reached, reached_exit=reached[-1],
        remaining_by_zone=occ[-1], in_transit_end=transit[-1]))
    r = check_run(g, s, P, run)
    assert r.ok, r.violations


def test_negative_occupancy_fails():
    g, s, run = _honest()
    occ = [dict(o) for o in run.zone_occupancy]
    occ[5]["Z1"] = -1
    occ[5]["Z2"] += 1
    r = check_run(g, s, P, _mut(run, zone_occupancy=occ))
    assert not r.ok
    assert any("Z1" in m and "negative" in m for m in r.violations)


def test_reached_decreasing_fails():
    g, s, run = _honest()
    reached = list(run.reached_by_step)
    reached[7] = reached[6] - 1
    r = check_run(g, s, P, _mut(run, reached_by_step=reached))
    assert not r.ok
    assert any("decreased" in m for m in r.violations)


def test_unknown_door_fails():
    g, s, run = _honest()
    flows = {k: list(v) for k, v in run.door_flows.items()}
    flows["D9"] = [0] * len(flows["D1"])
    r = check_run(g, s, P, _mut(run, door_flows=flows))
    assert not r.ok and any("D9" in m for m in r.violations)


def _two_zone_graph(d2_state="open"):
    return VenueGraph(
        schema_version="1", video_sha256="t", anchor=None,
        zones=[_zone("Z1", (0, 0, 10, 10), 0), _zone("Z2", (10, 0, 10, 10), 5)],
        doors=[_door("D1", "Z1", "OUTSIDE", 1.0, (0, 5)),
               _door("D2", "Z1", "Z2", 1.2, (10, 5), kind="door", state=d2_state)],
        keyframes=[])


def test_departure_before_presence_fails():
    # Z1 empty, Z2 has 5. Someone walks Z2->Z1 at k=0 while someone "exits" Z1 at k=0.
    g, s = _two_zone_graph(), Scenario()
    base = solve(g, s, P)
    K = P.horizon_s // P.dt_s
    from walktwin.checker import _travel
    cents = {"Z1": (5, 5), "Z2": (15, 5)}
    t2 = _travel(g.doors[1], cents, P)
    t1 = _travel(g.doors[0], cents, P)
    f1, f2 = [0] * K, [0] * K
    f1[0] = 1       # exit from Z1 (empty)
    f2[0] = -1      # Z2 -> Z1 (b -> a)
    occ, tr, re = [], [], []
    for k in range(K + 1):
        z1 = z2 = 0
        z2 = 5 - (1 if k >= 1 else 0)
        z1 = (1 if k >= t2 else 0) - (1 if k >= 1 else 0)
        occ.append({"Z1": z1, "Z2": z2})
        tr.append(sum(1 for j, a in ((0, t1), (0, t2)) if j < k < j + a) )
        re.append(1 if k >= t1 else 0)
    run = base.model_copy(update=dict(
        door_flows={"D1": f1, "D2": f2}, zone_occupancy=occ, transit_by_step=tr,
        reached_by_step=re, reached_exit=re[-1], remaining_by_zone=occ[-1],
        in_transit_end=tr[-1]))
    r = check_run(g, s, P, run)
    assert not r.ok
    assert any("Z1" in m and "conservation" in m and "only 0 present" in m
               for m in r.violations), r.violations


def test_flow_on_not_open_interior_door_fails():
    g, s = _two_zone_graph(d2_state="closed"), Scenario()
    run = solve(g, s, P)
    flows = {k: list(v) for k, v in run.door_flows.items()}
    flows["D2"][0] = -1
    r = check_run(g, s, P, run.model_copy(update=dict(door_flows=flows)))
    assert not r.ok
    assert any("D2" in m and "closed" in m for m in r.violations)


def test_inward_flow_on_exit_fails():
    g, s, run = _honest()
    flows = {k: list(v) for k, v in run.door_flows.items()}
    flows["D1"][0] = -1
    r = check_run(g, s, P, _mut(run, door_flows=flows))
    assert not r.ok
    assert any("D1" in m and "conservation" in m and "inward" in m for m in r.violations)


def test_departure_after_horizon_fails():
    g, s, run = _honest()
    K = P.horizon_s // P.dt_s
    flows = {k: list(v) for k, v in run.door_flows.items()}
    flows["D1"][K - 1] = 1
    r = check_run(g, s, P, _mut(run, door_flows=flows))
    assert not r.ok
    assert any("D1" in m and "after horizon" in m for m in r.violations)


def test_negative_occupancy_single_message():
    g, s, run = _honest()
    occ = [dict(o) for o in run.zone_occupancy]
    occ[5]["Z1"] = -1
    r = check_run(g, s, P, _mut(run, zone_occupancy=occ))
    assert sum(1 for m in r.violations if "Z1" in m and "step 5" in m and "negative" in m) == 1
