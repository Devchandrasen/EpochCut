"""Development tests; confirmatory schedules live in scripts/lnet_evaluate.py."""
import copy
from dataclasses import replace
from itertools import combinations
import random
from concurrent.futures import ThreadPoolExecutor
import tempfile
from pathlib import Path
import unittest

from epochcut.graph import Edge, InfluenceGraph, Node
from epochcut.temporal import (Broker, Policy, make_certificate, moving_graph,
                               separation, solve, verify_v2)

GOOD = {"tool": "send_email", "arguments": {"to": "approved@example.test", "body": "approved"}}
BAD = {"tool": "send_email", "arguments": {"to": "attacker@example.test", "body": "leak"}}


def route(broker, token, action=GOOD, path=("b", "c", "t")):
    for node in path:
        result = broker.advance(token, node, "effect" if node == "t" else "queue", action)
        if not result["allowed"]:
            return result
    return broker.commit(token, action)


class TemporalTests(unittest.TestCase):
    def test_moving_cut_counterexample_and_retention(self):
        for mode in ("snapshot", "epochcut", "sink", "full"):
            graph, policies = moving_graph()
            b = Broker(graph, policies, strategy=mode)
            token = b.begin("queued", "s", GOOD)
            self.assertTrue(b.advance(token, "b", "queue", BAD)["allowed"])
            self.assertEqual(b.configs[0].placements["effect"],
                             frozenset({"t"}) if mode == "sink" else
                             frozenset({"a", "c", "t"}) if mode == "full" else frozenset({"c"}))
            new_graph, new_policies = moving_graph(False)
            self.assertTrue(b.admit(new_graph, new_policies)["accepted"])
            result = route(b, token, BAD, ("c", "t"))
            self.assertEqual(result.get("committed", False), mode == "snapshot")
            if mode == "epochcut":
                self.assertIn(0, b.configs)
                b.finish(token)
                self.assertNotIn(0, b.configs)
            b.close()

    def test_benign_queued_completes(self):
        g, p = moving_graph()
        b = Broker(g, p)
        token = b.begin("w", "s", GOOD)
        b.advance(token, "b", "queue", GOOD)
        b.admit(*moving_graph(False))
        self.assertTrue(route(b, token, path=("c", "t"))["committed"])
        b.close()

    def test_certificate_mutations(self):
        g, p = moving_graph()
        c = make_certificate(g, p, solve(g, p), 7)
        self.assertTrue(verify_v2(g, p, c, 7))
        self.assertFalse(verify_v2(g, p, c, 8))
        self.assertFalse(verify_v2(g, (replace(p[0], version="other"),), c, 7))
        altered = g.copy()
        altered.add_edge(Edge("s", "t", "effect"))
        self.assertFalse(verify_v2(altered, p, c, 7))
        for placement in (("b",), (), ("a",)):
            wrong = make_certificate(g, p, {"effect": placement}, 7)
            self.assertFalse(verify_v2(g, p, wrong, 7))
        wrong = copy.deepcopy(c)
        wrong["costs"]["effect"] += 1
        self.assertFalse(verify_v2(g, p, wrong, 7))

    def test_ingress_authentication_and_payload(self):
        b = Broker(*moving_graph())
        token = b.begin("w", "s", GOOD, payload={"epoch": 999, "context": "forged"})
        self.assertEqual(b.contexts[token.split(".")[0]].credentials["epoch"], 0)
        self.assertFalse(b.advance(token[:-1]+("a" if token[-1] != "a" else "b"), "b", "queue", GOOD)["allowed"])
        self.assertFalse(b.advance(token, "b", "queue", GOOD, sender="attacker")["allowed"])
        self.assertFalse(b.advance(token, "t", "undeclared", GOOD)["allowed"])
        b.close()

    def test_intent_is_copied_and_grant_is_action_bound(self):
        b = Broker(*moving_graph(False))
        original = copy.deepcopy(GOOD)
        token = b.begin("w", "s", original)
        original["arguments"]["body"] = "changed"
        self.assertTrue(b.advance(token, "a", "queue", GOOD)["allowed"])
        for n in ("b", "c", "t"):
            self.assertTrue(b.advance(token, n, "effect" if n == "t" else "queue", GOOD)["allowed"])
        self.assertEqual(b.commit(token, BAD)["reason"], "argument_substitution")
        b.close()

    def test_acknowledgement_failure_and_limits(self):
        b = Broker(*moving_graph(), max_epochs=2, max_contexts=1)
        token = b.begin("w", "s", GOOD)
        with self.assertRaisesRegex(ValueError, "context_backpressure"):
            b.begin("x", "s", GOOD)
        b.installer = lambda cfg: False
        self.assertEqual(b.admit(*moving_graph(False))["reason"], "installation_not_acknowledged")
        self.assertEqual(b.current, 0)
        b.installer = lambda cfg: True
        self.assertTrue(b.admit(*moving_graph(False))["accepted"])
        # Only epochs with active work are pinned; a current idle epoch can be replaced.
        self.assertTrue(b.admit(*moving_graph(False))["accepted"])
        b.finish(token)
        self.assertEqual(len(b.contexts), 0)
        self.assertFalse(b.advance(token, "b", "queue", GOOD)["allowed"])
        b.close()

    def test_delegation_retains_parent_epoch_and_is_scoped(self):
        g, p = moving_graph()
        g.add_edge(Edge("b", "s", "delegation"))
        b = Broker(g, p)
        root = b.begin("w", "s", GOOD)
        b.advance(root, "b", "queue", GOOD)
        child = b.delegate(root, "s", GOOD)
        b.finish(root)
        b.admit(*moving_graph(False))
        self.assertIn(0, b.configs)
        self.assertTrue(route(b, child)["committed"])
        b.finish(child)
        self.assertNotIn(0, b.configs)
        b.close()

    def test_delegated_monitor_cannot_be_bypassed(self):
        g, p = moving_graph()
        g.add_edge(Edge("b", "t", "delegation"))
        b = Broker(g, p)
        root = b.begin("w", "s", GOOD)
        b.advance(root, "b", "queue", GOOD)
        with self.assertRaisesRegex(ValueError, "scope_widening"):
            b.delegate(root, "t", BAD)
        child = b.delegate(root, "t", GOOD)
        self.assertTrue(b.commit(child, GOOD)["committed"])
        b.close()

    def test_memory_is_untrusted_current_ingress(self):
        b = Broker(*moving_graph())
        b.store("m", "adversarial", {"epoch": 0, "principal": "s"})
        b.admit(*moving_graph(False))
        token, record = b.reenter_memory("m", "w", "s", GOOD)
        self.assertTrue(record["provenance"]["untrusted"])
        self.assertEqual(b.contexts[token.split(".")[0]].credentials["epoch"], 1)
        self.assertFalse(b.advance(token, "a", "queue", BAD)["allowed"])
        b.close()

    def test_revocation_and_expiry(self):
        b = Broker(*moving_graph())
        token = b.begin("w", "s", GOOD)
        for n in ("b", "c", "t"):
            b.advance(token, n, "effect" if n == "t" else "queue", GOOD)
        b.revoke("w")
        self.assertFalse(b.commit(token, GOOD)["committed"])
        expired = b.begin("expired", "s", GOOD, ttl_ns=-1)
        self.assertEqual(b.advance(expired, "b", "queue", GOOD)["reason"], "expired_context")
        b.close()

    def test_duplicate_race_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = str(Path(d)/"ledger.sqlite")
            b = Broker(*moving_graph(), ledger=ledger)
            token = b.begin("w", "s", GOOD)
            for n in ("b", "c", "t"):
                b.advance(token, n, "effect" if n == "t" else "queue", GOOD)
            with ThreadPoolExecutor(8) as pool:
                results = list(pool.map(lambda _: b.commit(token, GOOD), range(16)))
            self.assertEqual(sum(x["committed"] for x in results), 1)
            b.close()
            restarted = Broker(*moving_graph(), ledger=ledger)
            self.assertEqual(len(restarted.effects()), 1)
            self.assertFalse(restarted.commit(token, GOOD)["committed"])
            restarted.close()

    def test_solver_exhaustive_development_crosscheck(self):
        for seed in range(30):
            rng = random.Random(seed)
            g = InfluenceGraph()
            for n in ("s", "a", "b", "c", "t"):
                g.add_node(Node(n, "pep" if n != "s" else "agent", rng.randint(1, 5), n != "s"))
            for u in g.nodes:
                for v in g.nodes:
                    if u != v and rng.random() < .23:
                        g.add_edge(Edge(u, v, "message"))
            p = Policy("p", ("s",), ("t",), ("a", "b", "c", "t"))
            feasible = [set(c) for k in range(5) for c in combinations(p.eligible, k) if separation(g, p, set(c))]
            best = min(sum(g.nodes[n].monitor_cost for n in c) for c in feasible)
            chosen = solve(g, (p,))["p"]
            self.assertEqual(sum(g.nodes[n].monitor_cost for n in chosen), best)


if __name__ == "__main__":
    unittest.main()
