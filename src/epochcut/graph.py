"""Typed influence graph used by EpochCut.

The graph deliberately contains no language-model logic.  It records the
security-relevant interfaces through which influence can move.  A deployment
adapter is responsible for making this graph complete.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Iterable


@dataclass(frozen=True, order=True)
class Node:
    name: str
    kind: str
    monitor_cost: int = 1
    monitorable: bool = True


@dataclass(frozen=True, order=True)
class Edge:
    source: str
    target: str
    interface: str


@dataclass(frozen=True)
class RiskPolicy:
    name: str
    source_kinds: frozenset[str]
    sink_kinds: frozenset[str]


@dataclass(frozen=True)
class Mutation:
    mutation_id: str
    add_nodes: tuple[Node, ...] = ()
    add_edges: tuple[Edge, ...] = ()
    remove_edges: tuple[Edge, ...] = ()
    adversarial: bool = False


@dataclass
class InfluenceGraph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: set[Edge] = field(default_factory=set)

    def copy(self) -> "InfluenceGraph":
        return InfluenceGraph(nodes=dict(self.nodes), edges=set(self.edges))

    def add_node(self, node: Node) -> None:
        if node.name in self.nodes and self.nodes[node.name] != node:
            raise ValueError(f"node redefinition: {node.name}")
        self.nodes[node.name] = node

    def add_edge(self, edge: Edge) -> None:
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise ValueError(f"edge endpoint missing: {edge}")
        self.edges.add(edge)

    def apply(self, mutation: Mutation) -> None:
        for edge in mutation.remove_edges:
            self.edges.discard(edge)
        for node in mutation.add_nodes:
            self.add_node(node)
        for edge in mutation.add_edges:
            self.add_edge(edge)

    def sources(self, policy: RiskPolicy) -> set[str]:
        return {n.name for n in self.nodes.values() if n.kind in policy.source_kinds}

    def sinks(self, policy: RiskPolicy) -> set[str]:
        return {n.name for n in self.nodes.values() if n.kind in policy.sink_kinds}

    def adjacency(self, excluded: Iterable[str] = ()) -> dict[str, set[str]]:
        blocked = set(excluded)
        out = {name: set() for name in self.nodes if name not in blocked}
        for edge in self.edges:
            if edge.source not in blocked and edge.target not in blocked:
                out[edge.source].add(edge.target)
        return out

    def has_path(self, sources: Iterable[str], sinks: Iterable[str], excluded: Iterable[str] = ()) -> bool:
        blocked = set(excluded)
        targets = set(sinks) - blocked
        frontier = list(set(sources) - blocked)
        seen = set(frontier)
        adj = self.adjacency(blocked)
        while frontier:
            current = frontier.pop()
            if current in targets:
                return True
            for nxt in adj.get(current, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
        return False

    def canonical_dict(self) -> dict[str, object]:
        return {
            "nodes": [
                {
                    "name": n.name,
                    "kind": n.kind,
                    "monitor_cost": n.monitor_cost,
                    "monitorable": n.monitorable,
                }
                for n in sorted(self.nodes.values())
            ],
            "edges": [
                {"source": e.source, "target": e.target, "interface": e.interface}
                for e in sorted(self.edges)
            ],
        }

    def digest(self) -> str:
        payload = json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode("utf-8")).hexdigest()

