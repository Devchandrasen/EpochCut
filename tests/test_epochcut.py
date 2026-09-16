from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from epochcut.benchmark import POLICIES, build_scenario  # noqa: E402
from epochcut.engine import EpochCutEngine, verify_certificate  # noqa: E402
from epochcut.graph import Edge, InfluenceGraph, Mutation, Node, RiskPolicy  # noqa: E402
from epochcut.maxflow import minimum_vertex_cut  # noqa: E402


class MinimumCutTests(unittest.TestCase):
    def test_weighted_vertex_cut_prefers_cheaper_node(self) -> None:
        graph = InfluenceGraph()
        for node in (
            Node("source", "untrusted", monitorable=False),
            Node("expensive", "agent", monitor_cost=7),
            Node("cheap", "agent", monitor_cost=2),
            Node("sink", "effect", monitor_cost=12),
        ):
            graph.add_node(node)
        graph.add_edge(Edge("source", "expensive", "input"))
        graph.add_edge(Edge("expensive", "cheap", "message"))
        graph.add_edge(Edge("cheap", "sink", "tool"))
        result = minimum_vertex_cut(graph, {"source"}, {"sink"})
        self.assertEqual(result.nodes, frozenset({"cheap"}))
        self.assertEqual(result.cost, 2)
        self.assertFalse(graph.has_path({"source"}, {"sink"}, excluded=result.nodes))

    def test_parallel_paths_require_both_branches(self) -> None:
        graph = InfluenceGraph()
        for node in (
            Node("source", "untrusted", monitorable=False),
            Node("a", "agent", monitor_cost=1),
            Node("b", "agent", monitor_cost=1),
            Node("sink", "effect", monitor_cost=12),
        ):
            graph.add_node(node)
        for edge in (
            Edge("source", "a", "input"),
            Edge("source", "b", "input"),
            Edge("a", "sink", "tool"),
            Edge("b", "sink", "tool"),
        ):
            graph.add_edge(edge)
        result = minimum_vertex_cut(graph, {"source"}, {"sink"})
        self.assertEqual(result.nodes, frozenset({"a", "b"}))
        self.assertEqual(result.cost, 2)


class EpochTests(unittest.TestCase):
    def test_mutation_and_cut_commit_atomically(self) -> None:
        policy = RiskPolicy("effect", frozenset({"untrusted"}), frozenset({"effect"}))
        graph = InfluenceGraph()
        for node in (
            Node("source", "untrusted", monitorable=False),
            Node("agent", "agent", monitor_cost=1),
            Node("sink", "effect", monitor_cost=12),
        ):
            graph.add_node(node)
        graph.add_edge(Edge("source", "agent", "input"))
        graph.add_edge(Edge("agent", "sink", "tool"))
        engine = EpochCutEngine(graph, (policy,))
        mutation = Mutation(
            "join",
            add_nodes=(Node("source2", "untrusted", monitorable=False), Node("agent2", "agent", monitor_cost=1)),
            add_edges=(Edge("source2", "agent2", "input"), Edge("agent2", "sink", "tool")),
            adversarial=True,
        )
        decision = engine.propose(mutation)
        self.assertTrue(decision.accepted)
        self.assertTrue(engine.is_closed())
        self.assertEqual(decision.epoch, 1)
        self.assertEqual(decision.certificates[0].graph_digest, engine.graph.digest())
        self.assertTrue(verify_certificate(engine.graph, policy, decision.certificates[0]))

    def test_certificate_rejects_graph_drift(self) -> None:
        policy = RiskPolicy("effect", frozenset({"untrusted"}), frozenset({"effect"}))
        graph = InfluenceGraph()
        for node in (
            Node("source", "untrusted", monitorable=False),
            Node("agent", "agent", monitor_cost=1),
            Node("sink", "effect", monitor_cost=12),
        ):
            graph.add_node(node)
        graph.add_edge(Edge("source", "agent", "input"))
        graph.add_edge(Edge("agent", "sink", "tool"))
        engine = EpochCutEngine(graph, (policy,))
        certificate = engine.certificates[0]
        drifted = graph.copy()
        drifted.add_node(Node("agent2", "agent", monitor_cost=1))
        drifted.add_edge(Edge("source", "agent2", "input"))
        drifted.add_edge(Edge("agent2", "sink", "tool"))
        self.assertFalse(verify_certificate(drifted, policy, certificate))

    def test_scenario_keeps_epochcut_closed(self) -> None:
        scenario = build_scenario(8, "tree", 20, 101)
        engine = EpochCutEngine(scenario.graph, POLICIES)
        for mutation in scenario.mutations:
            decision = engine.propose(mutation)
            self.assertTrue(decision.accepted)
            self.assertTrue(engine.is_closed())


if __name__ == "__main__":
    unittest.main()
