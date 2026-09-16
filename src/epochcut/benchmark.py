"""Controlled dynamic-topology benchmark for EpochCut."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path
import random
from time import perf_counter_ns

from .engine import EpochCutEngine
from .graph import Edge, InfluenceGraph, Mutation, Node, RiskPolicy
from .maxflow import minimum_vertex_cut


POLICIES = (
    RiskPolicy("durable_effect", frozenset({"untrusted"}), frozenset({"effect"})),
    RiskPolicy("authority_transfer", frozenset({"untrusted"}), frozenset({"authority"})),
    RiskPolicy("persistent_state", frozenset({"untrusted"}), frozenset({"persistent"})),
)


@dataclass(frozen=True)
class Scenario:
    graph: InfluenceGraph
    mutations: tuple[Mutation, ...]


def _connect_topology(graph: InfluenceGraph, agents: list[str], topology: str, rng: random.Random) -> None:
    if topology == "chain":
        pairs = zip(agents[:-1], agents[1:])
    elif topology == "ring":
        pairs = zip(agents, agents[1:] + agents[:1])
    elif topology == "star":
        pairs = ((agents[0], agent) for agent in agents[1:])
    elif topology == "tree":
        pairs = ((agents[(i - 1) // 2], agents[i]) for i in range(1, len(agents)))
    elif topology == "random":
        pairs = ((agents[i], agents[j]) for i in range(len(agents)) for j in range(len(agents)) if i != j and rng.random() < 2.5 / max(2, len(agents)))
    else:
        raise ValueError(topology)
    for source, target in pairs:
        graph.add_edge(Edge(source, target, "message"))


def build_scenario(agent_count: int, topology: str, mutation_count: int, seed: int) -> Scenario:
    rng = random.Random(seed)
    graph = InfluenceGraph()
    graph.add_node(Node("external_0", "untrusted", monitorable=False))
    agents = [f"agent_{i}" for i in range(agent_count)]
    for index, agent in enumerate(agents):
        graph.add_node(Node(agent, "agent", monitor_cost=1 + (index % 5)))
    _connect_topology(graph, agents, topology, rng)
    graph.add_edge(Edge("external_0", agents[0], "input"))

    for kind, name, anchor in (
        ("effect", "effect_0", agents[-1]),
        ("authority", "authority_0", agents[max(0, agent_count // 2)]),
        ("persistent", "persistent_0", agents[max(0, agent_count // 3)]),
    ):
        graph.add_node(Node(name, kind, monitor_cost=12))
        graph.add_edge(Edge(anchor, name, "protected_effect"))

    mutations: list[Mutation] = []
    live_agents = list(agents)
    live_sources = ["external_0"]
    live_sinks = ["effect_0", "authority_0", "persistent_0"]
    for step in range(mutation_count):
        attack = step % 2 == 1
        mutation_type = ("tool_return", "spawn", "shared_memory", "delegation", "reroute")[step % 5]
        add_nodes: list[Node] = []
        add_edges: list[Edge] = []
        if mutation_type == "tool_return":
            source = f"external_{len(live_sources)}"
            add_nodes.append(Node(source, "untrusted", monitorable=False))
            target = rng.choice(live_agents)
            add_edges.append(Edge(source, target, "tool_return"))
            if attack:
                add_edges.append(Edge(target, rng.choice(live_sinks), "tool_call"))
            live_sources.append(source)
        elif mutation_type == "spawn":
            parent = rng.choice(live_agents)
            child = f"agent_{len(live_agents)}"
            add_nodes.append(Node(child, "agent", monitor_cost=1 + (step % 5)))
            add_edges.append(Edge(parent, child, "spawn"))
            if attack:
                source = f"external_{len(live_sources)}"
                add_nodes.append(Node(source, "untrusted", monitorable=False))
                add_edges.append(Edge(source, child, "member_input"))
                add_edges.append(Edge(child, rng.choice(live_sinks), "tool_call"))
                live_sources.append(source)
            else:
                add_edges.append(Edge(child, parent, "result"))
            live_agents.append(child)
        elif mutation_type == "shared_memory":
            memory = f"memory_{step}"
            add_nodes.append(Node(memory, "memory", monitor_cost=2 + (step % 4)))
            source = rng.choice(live_sources)
            target = rng.choice(live_agents)
            add_edges.extend((Edge(source, memory, "memory_write"), Edge(memory, target, "memory_read")))
            if attack:
                add_edges.append(Edge(target, rng.choice(live_sinks), "tool_call"))
        elif mutation_type == "delegation":
            source_agent = rng.choice(live_agents)
            sink_kind = rng.choice(("effect", "authority", "persistent"))
            sink = f"{sink_kind}_{len(live_sinks)}"
            add_nodes.append(Node(sink, sink_kind, monitor_cost=12 + (step % 3)))
            add_edges.append(Edge(source_agent, sink, "delegated_effect"))
            if attack:
                source = f"external_{len(live_sources)}"
                add_nodes.append(Node(source, "untrusted", monitorable=False))
                add_edges.append(Edge(source, source_agent, "delegated_input"))
                live_sources.append(source)
            live_sinks.append(sink)
        else:
            source = rng.choice(live_sources if attack else live_agents)
            target = rng.choice(live_agents)
            add_edges.append(Edge(source, target, "reroute"))
            if attack:
                add_edges.append(Edge(target, rng.choice(live_sinks), "tool_call"))
        mutations.append(
            Mutation(
                mutation_id=f"{topology}-{agent_count}-{seed}-{step}",
                add_nodes=tuple(add_nodes),
                add_edges=tuple(add_edges),
                adversarial=attack,
            )
        )
    return Scenario(graph, tuple(mutations))


def _union_min_cut(graph: InfluenceGraph) -> frozenset[str]:
    cuts = [minimum_vertex_cut(graph, graph.sources(policy), graph.sinks(policy)).nodes for policy in POLICIES]
    return frozenset().union(*cuts)


def _closed(graph: InfluenceGraph, monitors: frozenset[str]) -> bool:
    return all(not graph.has_path(graph.sources(p), graph.sinks(p), excluded=monitors) for p in POLICIES)


def _monitor_cost(graph: InfluenceGraph, monitors: frozenset[str]) -> int:
    return sum(graph.nodes[n].monitor_cost for n in monitors if n in graph.nodes)


def evaluate_scenario(scenario: Scenario, periodic_interval: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    live = scenario.graph.copy()
    static_monitors = _union_min_cut(live)
    periodic_monitors = static_monitors
    epoch_engine = EpochCutEngine(live, POLICIES)

    for step, mutation in enumerate(scenario.mutations, start=1):
        live.apply(mutation)
        if step % periodic_interval == 0:
            periodic_monitors = _union_min_cut(live)
        epoch_decision = epoch_engine.propose(mutation)
        sink_monitors = frozenset(name for name, node in live.nodes.items() if node.kind in {"effect", "authority", "persistent"})
        full_monitors = frozenset(name for name, node in live.nodes.items() if node.monitorable)

        methods = {
            "startup-cut": (static_monitors, True, 0),
            f"periodic-{periodic_interval}": (periodic_monitors, True, 0),
            "sink-mediation": (sink_monitors, True, 0),
            "full-mediation": (full_monitors, True, 0),
            "epochcut": (epoch_decision.monitors, epoch_decision.accepted, epoch_decision.latency_ns),
        }
        for method, (monitors, accepted, latency_ns) in methods.items():
            evaluated_graph = epoch_engine.graph if method == "epochcut" else live
            is_closed = _closed(evaluated_graph, monitors)
            rows.append(
                {
                    "mutation_id": mutation.mutation_id,
                    "step": step,
                    "method": method,
                    "adversarial": int(mutation.adversarial),
                    "accepted": int(accepted),
                    "closed": int(is_closed),
                    "unsafe_accept": int(accepted and not is_closed),
                    "monitor_count": len(monitors),
                    "monitor_cost": _monitor_cost(evaluated_graph, monitors),
                    "node_count": len(evaluated_graph.nodes),
                    "edge_count": len(evaluated_graph.edges),
                    "admission_latency_ns": latency_ns,
                }
            )
    return rows


def run_protocol(protocol_path: Path) -> tuple[Path, Path]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    root = protocol_path.parent.parent
    raw_dir = root / "results" / "raw"
    analysis_dir = root / "results" / "analysis"
    raw_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    started = perf_counter_ns()
    for seed in protocol["seeds"]:
        for topology in protocol["topologies"]:
            for agent_count in protocol["agent_counts"]:
                scenario = build_scenario(agent_count, topology, protocol["mutations_per_scenario"], seed)
                scenario_rows = evaluate_scenario(scenario, protocol["periodic_interval"])
                for row in scenario_rows:
                    row.update({"seed": seed, "topology": topology, "initial_agents": agent_count})
                rows.extend(scenario_rows)

    raw_path = raw_dir / "dynamic_topology_results.csv"
    with raw_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    elapsed_ns = perf_counter_ns() - started
    summary = summarize(rows)
    summary["protocol"] = protocol
    summary["row_count"] = len(rows)
    summary["wall_time_ns"] = elapsed_ns
    summary_path = analysis_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return raw_path, summary_path


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    methods = sorted({str(row["method"]) for row in rows})
    summary: dict[str, object] = {"methods": {}}
    for method in methods:
        subset = [row for row in rows if row["method"] == method]
        adversarial = [row for row in subset if int(row["adversarial"]) == 1]
        benign = [row for row in subset if int(row["adversarial"]) == 0]
        latencies_ms = [int(row["admission_latency_ns"]) / 1e6 for row in subset if int(row["admission_latency_ns"]) > 0]
        summary["methods"][method] = {
            "unsafe_accept_rate_adversarial": sum(int(r["unsafe_accept"]) for r in adversarial) / len(adversarial),
            "closure_rate_all": sum(int(r["closed"]) for r in subset) / len(subset),
            "benign_accept_rate": sum(int(r["accepted"]) for r in benign) / len(benign),
            "mean_monitor_cost": sum(int(r["monitor_cost"]) for r in subset) / len(subset),
            "mean_monitor_count": sum(int(r["monitor_count"]) for r in subset) / len(subset),
            "p50_admission_latency_ms": _percentile(latencies_ms, 0.50),
            "p95_admission_latency_ms": _percentile(latencies_ms, 0.95),
            "p99_admission_latency_ms": _percentile(latencies_ms, 0.99),
            "n": len(subset),
        }
    return summary

