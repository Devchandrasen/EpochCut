"""Minimal executable walkthrough of transactional path closure."""

from __future__ import annotations

import json

from epochcut import (
    Edge,
    EpochCutEngine,
    InfluenceGraph,
    Mutation,
    Node,
    RiskPolicy,
    verify_certificate,
)


def main() -> None:
    graph = InfluenceGraph()
    for node in (
        Node("untrusted_doc", "untrusted", monitorable=False),
        Node("planner", "agent", monitor_cost=5),
        Node("effect_guard", "policy_gateway", monitor_cost=1),
        Node("email_service", "protected_effect", monitorable=False),
    ):
        graph.add_node(node)
    for edge in (
        Edge("untrusted_doc", "planner", "prompt"),
        Edge("planner", "effect_guard", "tool_request"),
        Edge("effect_guard", "email_service", "effect_commit"),
    ):
        graph.add_edge(edge)

    policy = RiskPolicy(
        "untrusted_to_effect",
        source_kinds=frozenset({"untrusted"}),
        sink_kinds=frozenset({"protected_effect"}),
    )
    engine = EpochCutEngine(graph, policies=(policy,))
    initial_certificate_valid = verify_certificate(
        engine.graph, policy, engine.certificates[0]
    )

    guarded_plugin = Mutation(
        "add_guarded_plugin_path",
        add_nodes=(Node("plugin_guard", "policy_gateway", monitor_cost=1),),
        add_edges=(
            Edge("planner", "plugin_guard", "delegation"),
            Edge("plugin_guard", "email_service", "effect_commit"),
        ),
    )
    admitted = engine.propose(guarded_plugin)

    direct_bypass = Mutation(
        "attempt_direct_bypass",
        add_edges=(Edge("untrusted_doc", "email_service", "undeclared_bypass"),),
        adversarial=True,
    )
    rejected = engine.propose(direct_bypass)

    print(
        json.dumps(
            {
                "initial_certificate_valid": initial_certificate_valid,
                "guarded_mutation": {
                    "accepted": admitted.accepted,
                    "epoch": admitted.epoch,
                    "monitors": sorted(admitted.monitors),
                },
                "direct_bypass": {
                    "accepted": rejected.accepted,
                    "epoch": rejected.epoch,
                    "reason": rejected.reason,
                },
                "live_graph_closed": engine.is_closed(),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
