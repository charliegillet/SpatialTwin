"""Pure-Python fallback when networkx is not importable in the sandbox: a "sandbox estimate".

It computes only the maximum number of modeled crossings, as a max flow from SOURCE to EXIT_COLLECTOR over the
checker's own rebuilt arc set (``checker_v2.expected_arcs``). The solver's first phase maximises the same count,
so the numbers agree whenever every path costs less than one completion (true for horizons under 100 steps), but
there is no schedule, no exposure and no independent check here. The local checker decides.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Tuple

from .checker_v2 import EXIT_COLLECTOR, SOURCE, SolveInputs, expected_arcs

LABEL = "sandbox estimate"


def max_completed(venue: Any, inputs: SolveInputs, horizon: int, dt: int) -> int:
    arcs = expected_arcs(venue, inputs, horizon, dt)
    index: Dict[Any, int] = {}

    def node(key: Any) -> int:
        if key not in index:
            index[key] = len(index)
        return index[key]

    graph: List[List[List[int]]] = []  # per node: [to, capacity, reverse index]

    def add(u: int, v: int, cap: int) -> None:
        while len(graph) <= max(u, v):
            graph.append([])
        graph[u].append([v, cap, len(graph[v])])
        graph[v].append([u, 0, len(graph[u]) - 1])

    for (u, v), cap in arcs.items():
        if cap > 0:
            add(node(u), node(v), int(cap))
    if SOURCE not in index or EXIT_COLLECTOR not in index:
        return 0
    s, t = index[SOURCE], index[EXIT_COLLECTOR]
    flow = 0
    while True:
        level = [-1] * len(graph)
        level[s] = 0
        queue = deque([s])
        while queue:
            u = queue.popleft()
            for v, cap, _ in graph[u]:
                if cap > 0 and level[v] < 0:
                    level[v] = level[u] + 1
                    queue.append(v)
        if level[t] < 0:
            return flow
        cursor = [0] * len(graph)

        def push(u: int, limit: int) -> int:
            if u == t:
                return limit
            while cursor[u] < len(graph[u]):
                edge = graph[u][cursor[u]]
                v, cap, rev = edge
                if cap > 0 and level[v] == level[u] + 1:
                    pushed = push(v, min(limit, cap))
                    if pushed:
                        edge[1] -= pushed
                        graph[v][rev][1] += pushed
                        return pushed
                cursor[u] += 1
            return 0

        while True:
            pushed = push(s, 1 << 30)
            if not pushed:
                break
            flow += pushed


def estimate_tuple(venue: Any, inputs: SolveInputs, horizon: int, dt: int) -> Tuple[int, str]:
    return max_completed(venue, inputs, horizon, dt), LABEL
