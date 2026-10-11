"""LNET protocol: trusted contexts, retained routes and a sandbox commit broker.

The original snapshot engine remains unchanged. Experimental strategies are
explicit controls; ``epochcut`` is the default operational protocol.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import hmac
import json
import secrets
import sqlite3
from threading import RLock
from time import perf_counter_ns, time_ns
from typing import Callable, Any

from .graph import Edge, InfluenceGraph, Node
from .maxflow import minimum_vertex_cut

VERSION = "lnet-v2.0"
STRATEGIES = ("native", "startup", "periodic", "sink", "full", "snapshot", "epochcut")
INTERFACES = frozenset({"input", "message", "queue", "tool", "effect", "memory_read", "delegation", "callback"})


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class Policy:
    name: str
    sources: tuple[str, ...]
    sinks: tuple[str, ...]
    eligible: tuple[str, ...]
    version: str = "intent-exact-v2"
    interfaces: tuple[str, ...] = tuple(sorted(INTERFACES))
    capabilities: tuple[str, ...] = ("final_arguments", "action_binding")
    cost_model: str = "one-time-shared-deployment;per-policy-execution"

    def descriptor(self) -> dict:
        return {**asdict(self), "rule": "exact-operation-and-all-arguments;one-intent-one-record"}

    def digest(self) -> str:
        return digest(self.descriptor())


def policy_graph(graph: InfluenceGraph, policy: Policy) -> InfluenceGraph:
    if not set(policy.sources + policy.sinks + policy.eligible) <= graph.nodes.keys():
        raise ValueError("unknown_policy_node")
    if set(policy.sources) & set(policy.eligible):
        raise ValueError("source_is_not_enforcement")
    if policy.capabilities != ("final_arguments", "action_binding"):
        raise ValueError("unsupported_policy_capability")
    out = InfluenceGraph()
    for node in graph.nodes.values():
        if node.monitor_cost <= 0 or ":" in node.name or node.name.startswith("__epochcut_"):
            raise ValueError("invalid_node_or_cost")
        eligible = node.name in policy.eligible
        if eligible and (node.kind != "pep" or not node.monitorable):
            raise ValueError("ineligible_enforcement_role")
        out.add_node(Node(node.name, node.kind, node.monitor_cost, eligible))
    for edge in graph.edges:
        if edge.interface not in INTERFACES:
            raise ValueError("unknown_interface")
        if edge.interface in policy.interfaces:
            out.add_edge(edge)
    return out


def separation(graph: InfluenceGraph, policy: Policy, monitors: set[str] | frozenset[str]) -> bool:
    filtered = policy_graph(graph, policy)
    return not filtered.has_path(policy.sources, policy.sinks, monitors)


def solve(graph: InfluenceGraph, policies: tuple[Policy, ...]) -> dict[str, frozenset[str]]:
    return {p.name: minimum_vertex_cut(policy_graph(graph, p), set(p.sources), set(p.sinks)).nodes for p in policies}


def make_certificate(graph: InfluenceGraph, policies: tuple[Policy, ...], placements: dict,
                     epoch: int, config: str = VERSION) -> dict:
    routes = [asdict(edge) for edge in sorted(graph.edges)]
    body = {
        "schema": "epochcut-certificate/2", "epoch": epoch,
        "graph_digest": graph.digest(), "routing_digest": digest(routes),
        "policy_digest": digest([p.descriptor() for p in policies]),
        "policies": [p.descriptor() for p in policies],
        "placements": {p.name: sorted(placements[p.name]) for p in policies},
        "costs": {p.name: sum(graph.nodes[n].monitor_cost for n in placements[p.name]) for p in policies},
        "implementation": VERSION, "configuration": config,
    }
    return {**body, "content_digest": digest(body)}


def verify_v2(graph: InfluenceGraph, policies: tuple[Policy, ...], certificate: dict,
              expected_epoch: int, config: str = VERSION) -> bool:
    """Check full binding and closure independently of solver residual state."""
    try:
        keys = {"schema", "epoch", "graph_digest", "routing_digest", "policy_digest", "policies",
                "placements", "costs", "implementation", "configuration", "content_digest"}
        if set(certificate) != keys or type(certificate["epoch"]) is not int:
            return False
        if certificate["epoch"] != expected_epoch or certificate["schema"] != "epochcut-certificate/2":
            return False
        placements = certificate["placements"]
        if set(placements) != {p.name for p in policies}:
            return False
        for policy in policies:
            selected = placements[policy.name]
            if selected != sorted(set(selected)) or not set(selected) <= set(policy.eligible):
                return False
            if not separation(graph, policy, set(selected)):
                return False
        expected = make_certificate(graph, policies, placements, expected_epoch, config)
        return hmac.compare_digest(canonical(expected), canonical(certificate))
    except (ValueError, KeyError, TypeError, AssertionError):
        return False


@dataclass
class Configuration:
    epoch: int
    graph: InfluenceGraph
    policies: tuple[Policy, ...]
    placements: dict[str, frozenset[str]]
    certificate: dict

    @property
    def monitors(self) -> frozenset[str]:
        return frozenset().union(*self.placements.values())

    @property
    def cost(self) -> int:
        return sum(self.graph.nodes[n].monitor_cost for n in self.monitors)


@dataclass
class Context:
    credentials: dict
    token: str
    node: str
    intent: dict | None
    state: str = "active"
    grants: dict[str, str] = field(default_factory=dict)
    parent: str | None = None


class Broker:
    """One authoritative serialized control/commit service.

    Context and grant authentication use standard HMAC-SHA256 with an ephemeral
    trusted service key. A restart loses contexts and rejects old credentials.
    SQLite records sandbox effects only, never arbitrary external side effects.
    """

    def __init__(self, graph: InfluenceGraph, policies: tuple[Policy, ...], *,
                 strategy: str = "epochcut", ledger: str = ":memory:",
                 max_epochs: int = 3, max_contexts: int = 128,
                 installer: Callable[[Configuration], bool] | None = None):
        if strategy not in STRATEGIES:
            raise ValueError("unknown_strategy")
        self.lock = RLock()
        self.key = secrets.token_bytes(32)
        self.strategy = strategy
        self.max_epochs, self.max_contexts = max_epochs, max_contexts
        self.installer = installer or (lambda _: True)
        self.contexts: dict[str, Context] = {}
        self.configs: dict[int, Configuration] = {}
        self.current = -1
        self.trace: list[dict] = []
        self.revoked: set[str] = set()
        self.unavailable: set[str] = set()
        self.steps = 0
        self.db = sqlite3.connect(ledger, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS effects (workflow TEXT, intent TEXT, request TEXT UNIQUE, action TEXT, epoch INTEGER, PRIMARY KEY(workflow,intent))")
        self.db.execute("CREATE TABLE IF NOT EXISTS memory (key TEXT PRIMARY KEY, value TEXT, provenance TEXT)")
        result = self.admit(graph, policies)
        if not result["accepted"]:
            raise ValueError(result["reason"])

    def event(self, event: str, ctx: Context | None = None, **fields) -> None:
        self.trace.append({"seq": len(self.trace), "time_ns": time_ns(), "event": event,
                           "current_epoch": self.current,
                           **({"context": ctx.credentials["request"], "workflow": ctx.credentials["workflow"],
                               "epoch": ctx.credentials["epoch"], "node": ctx.node} if ctx else {}), **fields})

    def _placements(self, graph: InfluenceGraph, policies: tuple[Policy, ...], epoch: int) -> dict:
        if self.strategy == "native":
            return {p.name: frozenset() for p in policies}
        if self.strategy == "sink":
            return {p.name: frozenset(set(p.sinks) & set(p.eligible)) for p in policies}
        if self.strategy == "full":
            return {p.name: frozenset(p.eligible) for p in policies}
        if epoch > 0 and (self.strategy == "startup" or (self.strategy == "periodic" and epoch % 5)):
            return {p.name: self.configs[self.current].placements.get(p.name, frozenset()) for p in policies}
        return solve(graph, policies)

    def _retire(self) -> None:
        active_epochs = {c.credentials["epoch"] for c in self.contexts.values() if c.state == "active"}
        for epoch in list(self.configs):
            if epoch != self.current and epoch not in active_epochs:
                del self.configs[epoch]
                self.event("retire", retired_epoch=epoch)
        # No stale credential can be revived: unknown request IDs fail closed.
        # Keep only active causal work, not an unbounded terminal-context cache.
        for request in list(self.contexts):
            if self.contexts[request].state != "active":
                del self.contexts[request]

    def admit(self, graph: InfluenceGraph, policies: tuple[Policy, ...], budget: int | None = None) -> dict:
        with self.lock:
            start = perf_counter_ns()
            self._retire()
            active_epochs = {c.credentials["epoch"] for c in self.contexts.values() if c.state == "active"}
            if len(active_epochs) + 1 > self.max_epochs:
                return self._admission_failure("retained_epoch_backpressure", start)
            epoch = self.current + 1
            try:
                for policy in policies:
                    policy_graph(graph, policy)
                solve_start = perf_counter_ns()
                placements = self._placements(graph, policies, epoch)
                solve_ns = perf_counter_ns() - solve_start
                union = frozenset().union(*placements.values())
                cost = sum(graph.nodes[n].monitor_cost for n in union)
                if budget is not None and cost > budget:
                    return self._admission_failure("chosen_union_budget_exceeded", start)
                hashing_start = perf_counter_ns()
                cert = make_certificate(graph, policies, placements, epoch)
                hashing_ns = perf_counter_ns() - hashing_start
                verify_start = perf_counter_ns()
                closed = verify_v2(graph, policies, cert, epoch)
                verify_ns = perf_counter_ns() - verify_start
                if self.strategy in {"sink", "full", "snapshot", "epochcut"} and not closed:
                    return self._admission_failure("nonseparating_placement", start)
                cfg = Configuration(epoch, graph.copy(), policies, placements, cert)
                install_start = perf_counter_ns()
                if not self.installer(cfg):
                    return self._admission_failure("installation_not_acknowledged", start)
                install_ns = perf_counter_ns() - install_start
            except (ValueError, AssertionError, KeyError) as exc:
                return self._admission_failure(str(exc), start)
            self.configs[epoch] = cfg
            self.current = epoch
            self.steps += 1
            self.event("activate", certificate=cert["content_digest"], monitors=sorted(union), closed=closed)
            self._retire()
            result = {"accepted": True, "reason": "admitted", "epoch": epoch, "closed": closed,
                      "cost": cost, "latency_ns": perf_counter_ns()-start, "solver_ns": solve_ns,
                      "verifier_ns": verify_ns, "hashing_ns": hashing_ns, "installation_ns": install_ns,
                      "queueing_ns": 0, "transition_wait_ns": 0,
                      "retained_epochs": len(self.configs), "retained_cost": sum(c.cost for c in self.configs.values())}
            return result

    def _admission_failure(self, reason: str, start: int) -> dict:
        self.event("admission_denied", reason=reason)
        return {"accepted": False, "reason": reason, "epoch": self.current, "latency_ns": perf_counter_ns()-start}

    def begin(self, workflow: str, source: str, intent: dict | None, *,
              ttl_ns: int = 60_000_000_000, payload: dict | None = None) -> str:
        with self.lock:
            cfg = self.configs[self.current]
            if workflow in self.revoked:
                raise ValueError("revoked_workflow")
            if source not in {s for p in cfg.policies for s in p.sources}:
                raise ValueError("undeclared_ingress")
            if sum(c.state == "active" for c in self.contexts.values()) >= self.max_contexts:
                raise ValueError("context_backpressure")
            request = secrets.token_hex(12)
            credentials = {"schema": "epochcut-context/2", "request": request, "workflow": workflow,
                           "principal": source, "audience": "sandbox-broker", "epoch": self.current,
                           "policy": cfg.certificate["policy_digest"], "expires_ns": time_ns()+ttl_ns,
                           "operations": ["send_email", "write_shared_memory", "delegate_scope"],
                           "resource_scope": "sandbox-ledger", "argument_scope": digest(intent)}
            mac = hmac.new(self.key, canonical(credentials), "sha256").hexdigest()
            token = request + "." + mac
            ctx = Context(credentials, token, source, json.loads(canonical(intent)))
            self.contexts[request] = ctx
            self.event("ingress", ctx, ignored_payload_context=bool(payload and any(k in payload for k in ("epoch", "context", "policy"))))
            return token

    def _context(self, token: str) -> Context:
        request, _, supplied_mac = token.partition(".")
        ctx = self.contexts.get(request)
        if ctx is None or not hmac.compare_digest(supplied_mac, hmac.new(self.key, canonical(ctx.credentials), "sha256").hexdigest()):
            raise ValueError("forged_or_unknown_context")
        if ctx.state != "active" or ctx.credentials["workflow"] in self.revoked:
            raise ValueError("cancelled_or_completed_context")
        if time_ns() >= ctx.credentials["expires_ns"]:
            ctx.state = "cancelled"
            self.event("expiry_cancel", ctx)
            self._retire()
            raise ValueError("expired_context")
        if ctx.credentials["epoch"] not in self.configs:
            raise ValueError("retired_epoch")
        return ctx

    def _configuration(self, ctx: Context) -> Configuration:
        return self.configs[ctx.credentials["epoch"] if self.strategy in {"epochcut", "sink", "full"} else self.current]

    def advance(self, token: str, target: str, interface: str, action: dict,
                sender: str | None = None) -> dict:
        with self.lock:
            try:
                ctx = self._context(token)
                cfg = self._configuration(ctx)
                if sender is not None and sender != ctx.node:
                    raise ValueError("principal_route_mismatch")
                edge = Edge(ctx.node, target, interface)
                if edge not in cfg.graph.edges:
                    raise ValueError("undeclared_or_cross_epoch_interface")
                for policy in cfg.policies:
                    if target in cfg.placements[policy.name]:
                        if target in self.unavailable:
                            raise ValueError("monitor_unavailable")
                        if ctx.intent is None or canonical(action) != canonical(ctx.intent):
                            self.event("policy_denied", ctx, target=target, reason="exact_intent_mismatch")
                            return {"allowed": False, "reason": "exact_intent_mismatch"}
                        ctx.grants[policy.name] = digest({"action": action, "request": ctx.credentials["request"],
                                                        "policy": policy.digest(), "epoch": ctx.credentials["epoch"]})
                        self.event("monitor", ctx, target=target, policy=policy.digest(), action=digest(action))
                previous = ctx.node
                ctx.node = target
                self.event("route", ctx, source=previous, target=target, interface=interface,
                           routing_epoch=cfg.epoch, action=digest(action))
                return {"allowed": True, "reason": "routed", "epoch": cfg.epoch}
            except ValueError as exc:
                self.event("route_denied", reason=str(exc))
                return {"allowed": False, "reason": str(exc)}

    def delegate(self, token: str, target: str, action: dict) -> str:
        """Create a causal child on an existing delegation edge; no authority widening."""
        with self.lock:
            parent = self._context(token)
            cfg = self._configuration(parent)
            if Edge(parent.node, target, "delegation") not in cfg.graph.edges:
                raise ValueError("undeclared_delegation")
            if parent.intent is not None and canonical(action) != canonical(parent.intent):
                raise ValueError("delegation_scope_widening")
            if sum(c.state == "active" for c in self.contexts.values()) >= self.max_contexts:
                raise ValueError("context_backpressure")
            request = secrets.token_hex(12)
            credentials = {**parent.credentials, "request": request, "principal": target}
            child_token = request + "." + hmac.new(self.key, canonical(credentials), "sha256").hexdigest()
            child = Context(credentials, child_token, target, parent.intent, parent=parent.credentials["request"])
            for policy in cfg.policies:
                if target in cfg.placements[policy.name]:
                    if target in self.unavailable:
                        raise ValueError("monitor_unavailable")
                    if child.intent is None or canonical(action) != canonical(child.intent):
                        raise ValueError("exact_intent_mismatch")
                    child.grants[policy.name] = digest({"action": action, "request": request,
                                                      "policy": policy.digest(), "epoch": credentials["epoch"]})
                    self.event("monitor", child, target=target, policy=policy.digest(), action=digest(action))
            self.contexts[request] = child
            self.event("delegate", child, parent=parent.credentials["request"], source=parent.node, target=target, interface="delegation")
            return child_token

    def commit(self, token: str, action: dict) -> dict:
        """Freshness + grant validation + nonce consumption + ledger record under one lock/transaction."""
        with self.lock:
            try:
                ctx = self._context(token)
                cfg = self._configuration(ctx)
                relevant = [p for p in cfg.policies if ctx.node in p.sinks]
                if not relevant or action.get("tool") not in ctx.credentials["operations"]:
                    raise ValueError("not_effect_or_scope")
                for policy in relevant:
                    grant = ctx.grants.get(policy.name)
                    expected = digest({"action": action, "request": ctx.credentials["request"],
                                       "policy": policy.digest(), "epoch": ctx.credentials["epoch"]})
                    if grant is not None and grant != expected:
                        raise ValueError("argument_substitution")
                    if self.strategy in {"epochcut", "sink", "full"} and grant != expected:
                        raise ValueError("missing_relevant_mediation")
                self.db.execute("BEGIN IMMEDIATE")
                try:
                    self.db.execute("INSERT INTO effects VALUES(?,?,?,?,?)", (
                        ctx.credentials["workflow"], "approved-intent", ctx.credentials["request"],
                        canonical(action).decode(), ctx.credentials["epoch"]))
                    self.db.execute("COMMIT")
                except sqlite3.IntegrityError:
                    self.db.execute("ROLLBACK")
                    self.event("duplicate_denied", ctx)
                    return {"committed": False, "reason": "nonce_or_intent_reuse"}
                except Exception:
                    self.db.execute("ROLLBACK")
                    raise
                self.event("commit", ctx, action=action, mediated=bool(ctx.grants))
                return {"committed": True, "reason": "sandbox_recorded"}
            except ValueError as exc:
                self.event("commit_denied", reason=str(exc))
                return {"committed": False, "reason": str(exc)}

    def finish(self, token: str, cancel: bool = False) -> None:
        with self.lock:
            ctx = self._context(token)
            ctx.state = "cancelled" if cancel else "completed"
            self.event(ctx.state, ctx)
            if cancel:
                pending = [ctx.credentials["request"]]
                while pending:
                    parent_id = pending.pop()
                    for child in self.contexts.values():
                        if child.parent == parent_id and child.state == "active":
                            child.state = "cancelled"
                            pending.append(child.credentials["request"])
                            self.event("cancelled", child)
            self._retire()

    def revoke(self, workflow: str) -> None:
        with self.lock:
            self.revoked.add(workflow)
            for ctx in self.contexts.values():
                if ctx.credentials["workflow"] == workflow and ctx.state == "active":
                    ctx.state = "cancelled"
            self.event("revoke_linearization", workflow=workflow)
            self._retire()

    def store(self, key: str, value: str, provenance: dict) -> None:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO memory VALUES(?,?,?)", (key, value, canonical({**provenance, "untrusted": True}).decode()))
            self.event("memory_store", key=key, provenance=provenance)

    def reenter_memory(self, key: str, workflow: str, source: str, intent: dict | None) -> tuple[str, dict]:
        with self.lock:
            record = self.db.execute("SELECT value,provenance FROM memory WHERE key=?", (key,)).fetchone()
            if record is None:
                raise ValueError("unknown_memory")
            token = self.begin(workflow, source, intent)
            ctx = self._context(token)
            self.event("memory_reentry", ctx, key=key, provenance=json.loads(record[1]))
            return token, {"value": record[0], "provenance": json.loads(record[1])}

    def effects(self) -> list[dict]:
        with self.lock:
            return [{"workflow": w, "intent": i, "request": r, "action": json.loads(a), "epoch": e}
                    for w, i, r, a, e in self.db.execute("SELECT * FROM effects ORDER BY rowid")]

    def statistics(self) -> dict:
        with self.lock:
            return {"retained_epochs": len(self.configs), "active_contexts": sum(c.state == "active" for c in self.contexts.values()),
                    "retained_cost": sum(c.cost for c in self.configs.values()),
                    "monitor_policy_pairs": sum(len(m) for c in self.configs.values() for m in c.placements.values()),
                    "context_bytes": sum(len(canonical({**c.credentials, "node": c.node, "grants": c.grants})) for c in self.contexts.values() if c.state == "active")}

    def close(self) -> None:
        self.db.close()


def moving_graph(shortcut: bool = True) -> tuple[InfluenceGraph, tuple[Policy, ...]]:
    graph = InfluenceGraph()
    for name, kind, cost, monitorable in (("s", "untrusted", 1, False), ("a", "pep", 1, True),
                                         ("b", "queue", 1, False), ("c", "pep", 2, True), ("t", "pep", 20, True)):
        graph.add_node(Node(name, kind, cost, monitorable))
    for source, target in (("s", "a"), ("a", "b"), ("b", "c"), ("c", "t")):
        graph.add_edge(Edge(source, target, "effect" if target == "t" else "queue"))
    if shortcut:
        graph.add_edge(Edge("s", "b", "queue"))
    policy = Policy("effect", ("s",), ("t",), ("a", "c", "t"))
    return graph, (policy,)
