"""Independent verifier for solver runs.

Deliberately does not import the solver. Effective width, cumulative-rule
capacity and travel steps are recomputed here from the contracts alone. The
checker enforces upper bounds (capacity, closures), arithmetic and
conservation; it does not require optimality, so lower flows are legal.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

from .contracts import Door, FlowParams, Scenario, VenueGraph

_OUT = "OUTSIDE"
_EPS = 1e-9


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    run_id: str
    violations: list[str] = field(default_factory=list)


def _fl(x: float) -> int:
    return math.floor(x + _EPS)


def _ce(x: float) -> int:
    return math.ceil(x - _EPS)


def _cap(door: Door, k: int, p: FlowParams) -> int:
    eff = max(0.0, door.clear_width.low_m - 2 * p.boundary_layer_m)
    c = p.specific_flow_p_per_m_s * eff * p.dt_s
    return _fl((k + 1) * c) - _fl(k * c)


def _travel(door: Door, centroids: dict[str, tuple[float, float]], p: FlowParams) -> int:
    def pt(z: str) -> tuple[float, float]:
        return door.position if z == _OUT else centroids[z]

    d = math.dist(pt(door.a), door.position) + math.dist(door.position, pt(door.b))
    return max(1, _ce(d / p.walk_speed_m_s / p.dt_s))


def _expected_run_id(revision: str, s_hash: str, p: FlowParams) -> str:
    pj = json.dumps(p.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return "r-" + hashlib.sha256((revision + s_hash + pj).encode("utf-8")).hexdigest()[:12]


def check_run(graph: VenueGraph, scenario: Scenario, params: FlowParams, run) -> CheckResult:
    v: list[str] = []
    K = params.horizon_s // params.dt_s

    if run.graph_revision != graph.revision:
        v.append(f"revision: run graph {run.graph_revision} != current {graph.revision}")
    if run.scenario_hash != scenario.hash:
        v.append(f"revision: run scenario {run.scenario_hash} != current {scenario.hash}")
    if run.params != params:
        v.append("revision: run params differ from checked params")
    if run.run_id != _expected_run_id(graph.revision, scenario.hash, params):
        v.append(f"revision: run_id {run.run_id} does not match inputs")

    zones = {z.id: z for z in graph.zones}
    zids = sorted(zones)
    centroids = {z.id: (z.rect[0] + z.rect[2] / 2, z.rect[1] + z.rect[3] / 2) for z in graph.zones}
    doors = {d.id: d for d in graph.doors}
    opened = {i.split(":", 1)[1] for i in scenario.interventions if i.startswith("OPEN:")}
    closed_from: dict[str, int] = {}
    for h in scenario.hazards:
        k0 = max(0, _ce(h.from_s / params.dt_s))
        closed_from[h.door_id] = min(k0, closed_from.get(h.door_id, k0))

    total = sum(z.occupants for z in graph.zones)
    if run.total != total:
        v.append(f"total: run total {run.total} != sum of occupants {total}")

    # Array shapes.
    shape_ok = True
    for name, arr in (("zone_occupancy", run.zone_occupancy),
                      ("transit_by_step", run.transit_by_step),
                      ("reached_by_step", run.reached_by_step)):
        if len(arr) != K + 1:
            v.append(f"conservation: {name} has length {len(arr)}, expected {K + 1}")
            shape_ok = False

    # Per-door checks and recomputation of movement.
    dep = {z: [0] * (K + 1) for z in zids}
    arr_ = {z: [0] * (K + 1) for z in zids}
    sink = [0] * (K + 1)
    transit_calc = [0] * (K + 2)
    flows_ok = True
    for did, flows in run.door_flows.items():
        d = doors.get(did)
        if d is None:
            v.append(f"door {did}: not in graph (kind unknown door)")
            flows_ok = False
            continue
        if len(flows) != K:
            v.append(f"door {did}: conservation, flow length {len(flows)} != {K}")
            flows_ok = False
            continue
        bad_ends = [e for e in (d.a, d.b) if e != _OUT and e not in zones]
        degenerate = d.a == d.b
        eff_open = d.state == "open" or did in opened
        is_exit = _OUT in (d.a, d.b)
        t = 1
        if not bad_ends and not degenerate:
            t = _travel(d, centroids, params)
        for k, f in enumerate(flows):
            if f == 0:
                continue
            if bad_ends or degenerate:
                v.append(f"door {did}: closed, flow {f} at step {k} on an unusable door")
                flows_ok = False
                continue
            if not eff_open:
                v.append(f"door {did}: closed, flow {f} at step {k} but door is not open")
            elif k >= closed_from.get(did, K + 1):
                v.append(f"door {did}: closed by hazard, flow {f} at step {k}")
            cap = _cap(d, k, params)
            if abs(f) > cap:
                v.append(f"door {did}: capacity exceeded at step {k}: |{f}| > {cap}")
            if is_exit:
                outward_ok = f > 0 if d.b == _OUT else f < 0
                if not outward_ok:
                    v.append(f"door {did}: conservation, inward flow {f} at exit step {k}")
                    flows_ok = False
                    continue
            if k + t > K:
                v.append(f"door {did}: conservation, departure at step {k} arrives after horizon")
                flows_ok = False
                continue
            n = abs(f)
            if is_exit:
                src = d.a if d.b == _OUT else d.b
                dep[src][k] += n
                sink[k + t] += n
            else:
                src, dst = (d.a, d.b) if f > 0 else (d.b, d.a)
                dep[src][k] += n
                arr_[dst][k + t] += n
            transit_calc[k + 1] += n
            transit_calc[k + t] -= n

    # Conservation / bookkeeping against reported arrays.
    if shape_ok and flows_ok:
        occ = {z: zones[z].occupants for z in zids}
        transit = reached = 0
        prev_reached = 0
        for k in range(K + 1):
            if k > 0:
                for z in zids:
                    occ[z] += arr_[z][k] - dep[z][k - 1]
            transit += transit_calc[k]
            reached += sink[k]
            rep = run.zone_occupancy[k]
            for z in zids:
                if rep.get(z) is not None and rep[z] < 0:
                    v.append(f"zone {z}: conservation, negative occupancy {rep[z]} at step {k}")
                if occ[z] < 0:
                    v.append(f"zone {z}: conservation, flows imply negative occupancy at step {k}")
                if rep.get(z) != occ[z]:
                    v.append(f"zone {z}: conservation, occupancy {rep.get(z)} at step {k} "
                             f"!= recomputed {occ[z]}")
            for z in rep:
                if z not in zones:
                    v.append(f"zone {z}: conservation, unknown zone in occupancy at step {k}")
            if run.transit_by_step[k] != transit:
                v.append(f"step {k}: conservation, transit {run.transit_by_step[k]} "
                         f"!= recomputed {transit}")
            if run.reached_by_step[k] != reached:
                v.append(f"step {k}: conservation, reached {run.reached_by_step[k]} "
                         f"!= recomputed {reached}")
            if run.reached_by_step[k] < prev_reached:
                v.append(f"step {k}: conservation, reached_by_step decreased")
            prev_reached = run.reached_by_step[k]
            s = sum(rep.values()) + run.transit_by_step[k] + run.reached_by_step[k]
            if s != total:
                v.append(f"step {k}: conservation, zones+transit+reached = {s} != total {total}")
        if run.reached_exit != reached:
            v.append(f"total: reached_exit {run.reached_exit} != exit inflow sum {reached}")
        if run.in_transit_end != transit:
            v.append(f"total: in_transit_end {run.in_transit_end} != recomputed {transit}")
        if dict(run.remaining_by_zone) != run.zone_occupancy[K]:
            v.append("total: remaining_by_zone != final zone_occupancy")
    elif shape_ok:
        # Flows unusable; still check what we can from reported arrays.
        for k in range(K + 1):
            s = sum(run.zone_occupancy[k].values()) + run.transit_by_step[k] + run.reached_by_step[k]
            if s != total:
                v.append(f"step {k}: conservation, zones+transit+reached = {s} != total {total}")
            if any(x < 0 for x in run.zone_occupancy[k].values()):
                v.append(f"step {k}: conservation, negative occupancy")
            if k and run.reached_by_step[k] < run.reached_by_step[k - 1]:
                v.append(f"step {k}: conservation, reached_by_step decreased")

    if shape_ok and run.reached_exit != run.reached_by_step[-1]:
        v.append(f"total: reached_exit {run.reached_exit} != reached_by_step[-1] "
                 f"{run.reached_by_step[-1]}")

    return CheckResult(ok=not v, run_id=run.run_id, violations=v)
