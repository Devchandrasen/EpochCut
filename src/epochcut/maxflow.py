"""Small deterministic max-flow implementation for weighted vertex cuts."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .graph import InfluenceGraph


@dataclass(frozen=True)
class CutResult:
    nodes: frozenset[str]
    cost: int


def _add_capacity(capacity: dict[str, dict[str, int]], u: str, v: str, value: int) -> None:
    capacity.setdefault(u, {})[v] = capacity.setdefault(u, {}).get(v, 0) + value
    capacity.setdefault(v, {}).setdefault(u, 0)


def minimum_vertex_cut(
    graph: InfluenceGraph,
    sources: set[str],
    sinks: set[str],
) -> CutResult:
    """Return a minimum-cost monitorable vertex cut.

    Sources cannot be selected.  Sinks are selectable, representing a trusted
    boundary adapter immediately before the protected effect.  Non-monitorable
    nodes receive infinite capacity.  Costs are positive integers to keep the
    certificate and solver deterministic.
    """

    if not sources or not sinks or not graph.has_path(sources, sinks):
        return CutResult(frozenset(), 0)

    finite_total = sum(max(1, n.monitor_cost) for n in graph.nodes.values())
    inf = finite_total + 1
    super_source = "__epochcut_super_source__"
    super_sink = "__epochcut_super_sink__"
    capacity: dict[str, dict[str, int]] = {}

    for name, node in graph.nodes.items():
        node_capacity = inf if name in sources or not node.monitorable else max(1, node.monitor_cost)
        _add_capacity(capacity, f"{name}:in", f"{name}:out", node_capacity)
    for edge in graph.edges:
        _add_capacity(capacity, f"{edge.source}:out", f"{edge.target}:in", inf)
    for source in sources:
        _add_capacity(capacity, super_source, f"{source}:in", inf)
    for sink in sinks:
        _add_capacity(capacity, f"{sink}:out", super_sink, inf)

    residual = {u: dict(vs) for u, vs in capacity.items()}
    max_flow = 0
    while True:
        parent: dict[str, str | None] = {super_source: None}
        queue = deque([super_source])
        while queue and super_sink not in parent:
            u = queue.popleft()
            for v in sorted(residual.get(u, {})):
                if residual[u][v] > 0 and v not in parent:
                    parent[v] = u
                    queue.append(v)
        if super_sink not in parent:
            break
        path_capacity = inf
        cursor = super_sink
        while parent[cursor] is not None:
            prev = parent[cursor]
            assert prev is not None
            path_capacity = min(path_capacity, residual[prev][cursor])
            cursor = prev
        cursor = super_sink
        while parent[cursor] is not None:
            prev = parent[cursor]
            assert prev is not None
            residual[prev][cursor] -= path_capacity
            residual[cursor][prev] = residual.get(cursor, {}).get(prev, 0) + path_capacity
            cursor = prev
        max_flow += path_capacity

    reachable = {super_source}
    queue = deque([super_source])
    while queue:
        u = queue.popleft()
        for v, value in residual.get(u, {}).items():
            if value > 0 and v not in reachable:
                reachable.add(v)
                queue.append(v)

    cut = {
        name
        for name, node in graph.nodes.items()
        if node.monitorable
        and name not in sources
        and f"{name}:in" in reachable
        and f"{name}:out" not in reachable
    }
    cost = sum(graph.nodes[name].monitor_cost for name in cut)
    if max_flow >= inf:
        raise ValueError("no finite monitorable cut exists")
    if cost != max_flow:
        raise AssertionError(f"cut/flow mismatch: cut={cost}, flow={max_flow}")
    return CutResult(frozenset(cut), cost)

