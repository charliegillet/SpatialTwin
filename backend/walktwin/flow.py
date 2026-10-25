"""Time-expanded max-flow egress solver.

The venue graph is unrolled into K = horizon_s // dt_s time steps. Nodes are
(zone, k) for k = 0..K plus a super-source and a super-sink. People wait in a
zone through unbounded holdover edges. Each effectively open door has one gate
per step whose capacity comes from the cumulative-rounding rule; that gate is
shared by both directions of an interior door, so capacity is per door, not per
direction. Exits carry flow outward only. People departing at step k arrive at
step k + travel_steps, and a gate exists only when that arrival is <= K.

The solver is ``nx.max_flow_min_cost`` with a lexicographic integer cost.
Each exit gate->sink edge costs (k + travel) * M, each interior door gate costs
1 per person per traversal, and holdovers cost 0. Every gate advances time by at
least one step, so one person makes at most K traversals, and the total
traversal cost is at most total * K < M. The arrival objective therefore
dominates, and door traversals only break ties. That removes zero-cost detours
into dead ends and back. Among all maximum flows the solver picks the one with
the least total arrival time and, within those, the fewest door traversals. In a time-expanded
network with a single sink an earliest-arrival flow exists, so this optimum
maximises the number reached at every step k at once: ``reached_by_step[k]``
equals the max-flow value at horizon k * dt_s.

Readback comes from the gate edge flows, after the returned flow has been
checked for capacity and conservation. Max-flow only sends people who reach
the sink by step K; everyone else stays in their starting zone. Two-way flow
through one interior gate in the same step (a swap, or a bounce back into the
same zone) is equivalent to those people holding over, so each interior
door-step is reduced to its net flow, signed a->b positive.
"""
from __future__ import annotations

import hashlib
import json
import math

import networkx as nx
from networkx.algorithms.flow import edmonds_karp
from pydantic import BaseModel, ConfigDict

from .contracts import Door, FlowParams, Scenario, VenueGraph, Zone

OUTSIDE = "OUTSIDE"
_EPS = 1e-9  # absorbs float error in floor/ceil of values that are exact in reals

_SOURCE = ("source",)
_SINK = ("sink",)


class FlowRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    graph_revision: str
    scenario_hash: str
    params: FlowParams
    total: int
    reached_exit: int
    remaining_by_zone: dict[str, int]
    in_transit_end: int
    door_flows: dict[str, list[int]]  # [d][k], k = 0..K-1, a->b positive
    zone_occupancy: list[dict[str, int]]  # [k], k = 0..K, start of step k
    transit_by_step: list[int]  # [k], k = 0..K, departed but not yet arrived
    reached_by_step: list[int]  # [k], k = 0..K, cumulative arrivals at exits


def _floor(x: float) -> int:
    return math.floor(x + _EPS)


def _ceil(x: float) -> int:
    return math.ceil(x - _EPS)


def door_rate_per_step(door: Door, params: FlowParams) -> float:
    """People per step through the door's effective (low-estimate) width."""
    effective_m = max(0.0, door.clear_width.low_m - 2 * params.boundary_layer_m)
    return params.specific_flow_p_per_m_s * effective_m * params.dt_s


def door_capacity_at_step(door: Door, k: int, params: FlowParams) -> int:
    """floor((k+1)*c) - floor(k*c): cumulative rounding loses < 1 person overall."""
    c = door_rate_per_step(door, params)
    return _floor((k + 1) * c) - _floor(k * c)


def _centroid(zone: Zone) -> tuple[float, float]:
    x, y, w, h = zone.rect
    return (x + w / 2, y + h / 2)


def _zone_point(graph: VenueGraph, zone: str | Zone, door: Door) -> tuple[float, float]:
    zid = zone.id if isinstance(zone, Zone) else zone
    if zid == OUTSIDE:
        return door.position
    for z in graph.zones:
        if z.id == zid:
            return _centroid(z)
    raise ValueError(f"zone {zid!r} not in graph")


def travel_steps(
    graph: VenueGraph, door: Door, from_zone: str | Zone, to_zone: str | Zone, params: FlowParams
) -> int:
    """Steps to walk centroid(from) -> door -> centroid(to) (door itself for OUTSIDE)."""
    p0 = _zone_point(graph, from_zone, door)
    p1 = _zone_point(graph, to_zone, door)
    dist = math.dist(p0, door.position) + math.dist(door.position, p1)
    return max(1, _ceil(dist / params.walk_speed_m_s / params.dt_s))


def _params_json(params: FlowParams) -> str:
    return json.dumps(params.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _run_id(graph_revision: str, scenario_hash: str, params: FlowParams) -> str:
    key = graph_revision + scenario_hash + _params_json(params)
    return "r-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _open_doors(graph: VenueGraph, scenario: Scenario) -> set[str]:
    door_ids = {d.id for d in graph.doors}
    opened = {i.split(":", 1)[1] for i in scenario.interventions if i.startswith("OPEN:")}
    unknown = sorted(opened - door_ids)
    if unknown:
        raise ValueError(f"OPEN intervention on unknown door id(s): {unknown}")
    return {d.id for d in graph.doors if d.state == "open" or d.id in opened}


def _closed_from_step(
    graph: VenueGraph, scenario: Scenario, params: FlowParams
) -> dict[str, int]:
    """Door id -> first step at which a hazard closes it."""
    door_ids = {d.id for d in graph.doors}
    out: dict[str, int] = {}
    for h in scenario.hazards:
        if h.door_id not in door_ids:
            raise ValueError(f"hazard on unknown door id {h.door_id!r}")
        k0 = max(0, _ceil(h.from_s / params.dt_s))
        out[h.door_id] = min(k0, out.get(h.door_id, k0))
    return out


def _validate_flow(G: nx.DiGraph, flow: dict) -> None:
    """Reject a solver result that breaks capacity, integrality or conservation."""
    for u, v, cap in G.edges(data="capacity"):
        f = flow[u][v]
        if not isinstance(f, int) or f < 0 or (cap is not None and f > cap):
            raise RuntimeError(f"invalid flow {f!r} on {u}->{v} (cap {cap})")
    for n in G.nodes:
        if n in (_SOURCE, _SINK):
            continue
        inflow = sum(flow[p][n] for p in G.predecessors(n))
        if inflow != sum(flow[n].values()):
            raise RuntimeError(f"flow not conserved at {n}")


def _zn(zid: str, k: int) -> tuple:
    return ("zone", zid, k)


def solve(graph: VenueGraph, scenario: Scenario, params: FlowParams) -> FlowRun:
    K = params.horizon_s // params.dt_s
    zones = sorted(graph.zones, key=lambda z: z.id)
    zone_ids = [z.id for z in zones]
    known = set(zone_ids)
    doors = sorted(graph.doors, key=lambda d: d.id)
    open_ids = _open_doors(graph, scenario)
    closed_from = _closed_from_step(graph, scenario, params)

    G = nx.DiGraph()
    G.add_node(_SOURCE)
    G.add_node(_SINK)
    for z in zones:
        for k in range(K + 1):
            G.add_node(_zn(z.id, k))
    for z in zones:
        if z.occupants > 0:
            G.add_edge(_SOURCE, _zn(z.id, 0), capacity=z.occupants)
        for k in range(K):
            G.add_edge(_zn(z.id, k), _zn(z.id, k + 1))  # holdover, unbounded

    total = sum(z.occupants for z in zones)
    M = total * K + 1  # > max total interior traversal cost (each person <= K)

    # Per door: (kind, inner zones, travel steps, list of gate steps).
    plan: dict[str, tuple[str, tuple[str, ...], int, list[int]]] = {}
    for d in doors:
        for end in (d.a, d.b):
            if end != OUTSIDE and end not in known:
                raise ValueError(f"door {d.id} references unknown zone {end!r}")
        if d.a == d.b or (d.a == OUTSIDE and d.b == OUTSIDE):
            continue
        if d.id not in open_ids:
            continue
        if OUTSIDE in (d.a, d.b):
            inner = d.b if d.a == OUTSIDE else d.a
            kind, ends, t = "exit", (inner,), travel_steps(graph, d, inner, OUTSIDE, params)
        else:
            kind, ends, t = "inner", (d.a, d.b), travel_steps(graph, d, d.a, d.b, params)
        last = min(K - t, closed_from.get(d.id, K + 1) - 1)
        steps = []
        for k in range(0, last + 1):
            cap = door_capacity_at_step(d, k, params)
            if cap <= 0:
                continue
            gin, gout = ("gate_in", d.id, k), ("gate_out", d.id, k)
            for zid in ends:
                G.add_edge(_zn(zid, k), gin)
            G.add_edge(gin, gout, capacity=cap, weight=0 if kind == "exit" else 1)
            if kind == "exit":
                G.add_edge(gout, _SINK, weight=(k + t) * M)  # arrival step dominates
            else:
                for zid in ends:
                    G.add_edge(gout, _zn(zid, k + t))
            steps.append(k)
        plan[d.id] = (kind, ends, t, steps)

    try:
        flow = nx.max_flow_min_cost(G, _SOURCE, _SINK)
    except (nx.NetworkXUnfeasible, nx.NetworkXUnbounded) as exc:
        raise RuntimeError(f"min-cost flow failed: {exc}") from exc
    _validate_flow(G, flow)
    value = sum(flow[u][_SINK] for u in G.predecessors(_SINK))
    check = nx.maximum_flow_value(G, _SOURCE, _SINK, flow_func=edmonds_karp)
    if value != check:
        raise RuntimeError(f"min-cost flow value {value} != edmonds_karp value {check}")

    # Readback from gate edge flows.
    departures = {zid: [0] * (K + 1) for zid in zone_ids}
    arrivals = {zid: [0] * (K + 1) for zid in zone_ids}
    sink_arrivals = [0] * (K + 1)
    transit_delta = [0] * (K + 2)  # difference array over steps
    door_flows: dict[str, list[int]] = {d.id: [0] * K for d in doors}

    for d in doors:
        if d.id not in plan:
            continue
        kind, ends, t, steps = plan[d.id]
        for k in steps:
            gin, gout = ("gate_in", d.id, k), ("gate_out", d.id, k)
            if kind == "exit":
                (inner,) = ends
                n = flow[_zn(inner, k)][gin]
                if n == 0:
                    continue
                departures[inner][k] += n
                sink_arrivals[k + t] += n
                door_flows[d.id][k] = n if d.b == OUTSIDE else -n
            else:
                a, b = ends
                x_a, x_b = flow[_zn(a, k)][gin], flow[_zn(b, k)][gin]
                y_a, y_b = flow[gout][_zn(a, k + t)], flow[gout][_zn(b, k + t)]
                n = x_a - y_a
                if n != y_b - x_b:
                    raise RuntimeError(f"gate {d.id}@{k} violates conservation")
                if n == 0:
                    continue
                src, dst = (a, b) if n > 0 else (b, a)
                departures[src][k] += abs(n)
                arrivals[dst][k + t] += abs(n)
                door_flows[d.id][k] = n
            transit_delta[k + 1] += abs(n)  # in transit for steps k+1 .. k+t-1
            transit_delta[k + t] -= abs(n)

    occ = {z.id: z.occupants for z in zones}
    zone_occupancy: list[dict[str, int]] = []
    transit_by_step: list[int] = []
    reached_by_step: list[int] = []
    transit = reached = 0
    for k in range(K + 1):
        if k > 0:
            for zid in zone_ids:
                occ[zid] += arrivals[zid][k] - departures[zid][k - 1]
                if occ[zid] < 0:
                    raise RuntimeError(f"negative occupancy {zid}@{k}")
        transit += transit_delta[k]
        reached += sink_arrivals[k]
        zone_occupancy.append(dict(occ))
        transit_by_step.append(transit)
        reached_by_step.append(reached)

    if reached_by_step[K] != value:
        raise RuntimeError("readback disagrees with max-flow value")

    revision = graph.revision
    s_hash = scenario.hash
    return FlowRun(
        run_id=_run_id(revision, s_hash, params),
        graph_revision=revision,
        scenario_hash=s_hash,
        params=params,
        total=total,
        reached_exit=value,
        remaining_by_zone=dict(zone_occupancy[K]),
        in_transit_end=transit_by_step[K],
        door_flows=door_flows,
        zone_occupancy=zone_occupancy,
        transit_by_step=transit_by_step,
        reached_by_step=reached_by_step,
    )
