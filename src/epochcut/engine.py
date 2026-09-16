"""Transactional topology admission and closure certificates."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from time import perf_counter_ns

from .graph import InfluenceGraph, Mutation, RiskPolicy
from .maxflow import CutResult, minimum_vertex_cut


@dataclass(frozen=True)
class ClosureCertificate:
    epoch: int
    graph_digest: str
    policy: str
    monitors: tuple[str, ...]
    cut_cost: int
    certificate_digest: str


@dataclass(frozen=True)
class AdmissionDecision:
    accepted: bool
    reason: str
    epoch: int
    monitors: frozenset[str]
    cut_cost: int
    latency_ns: int
    certificates: tuple[ClosureCertificate, ...]


class EpochCutEngine:
    """Fail-closed graph epoch manager.

    A prospective graph is solved and independently verified before it replaces
    the live graph.  This ordering is the key safety property: topology and
    monitor placement change in one logical commit.
    """

    def __init__(
        self,
        graph: InfluenceGraph,
        policies: tuple[RiskPolicy, ...],
        monitor_budget: int | None = None,
    ) -> None:
        self.graph = graph.copy()
        self.policies = policies
        self.monitor_budget = monitor_budget
        self.epoch = 0
        cuts = self._solve(self.graph)
        self.monitors = frozenset().union(*(result.nodes for result in cuts.values()))
        self.certificates = self._certify(self.graph, cuts, self.epoch)

    def _solve(self, graph: InfluenceGraph) -> dict[str, CutResult]:
        return {
            policy.name: minimum_vertex_cut(graph, graph.sources(policy), graph.sinks(policy))
            for policy in self.policies
        }

    def _verify(self, graph: InfluenceGraph, cuts: dict[str, CutResult]) -> None:
        for policy in self.policies:
            cut = cuts[policy.name]
            if graph.has_path(graph.sources(policy), graph.sinks(policy), excluded=cut.nodes):
                raise AssertionError(f"unclosed path for {policy.name}")

    def _certify(
        self,
        graph: InfluenceGraph,
        cuts: dict[str, CutResult],
        epoch: int,
    ) -> tuple[ClosureCertificate, ...]:
        graph_digest = graph.digest()
        out = []
        for policy in self.policies:
            cut = cuts[policy.name]
            payload = {
                "epoch": epoch,
                "graph_digest": graph_digest,
                "policy": policy.name,
                "monitors": sorted(cut.nodes),
                "cut_cost": cut.cost,
            }
            digest = sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            out.append(
                ClosureCertificate(
                    epoch=epoch,
                    graph_digest=graph_digest,
                    policy=policy.name,
                    monitors=tuple(sorted(cut.nodes)),
                    cut_cost=cut.cost,
                    certificate_digest=digest,
                )
            )
        return tuple(out)

    def propose(self, mutation: Mutation) -> AdmissionDecision:
        started = perf_counter_ns()
        prospective = self.graph.copy()
        try:
            prospective.apply(mutation)
            cuts = self._solve(prospective)
            self._verify(prospective, cuts)
        except (ValueError, AssertionError) as exc:
            return AdmissionDecision(
                accepted=False,
                reason=f"closure_failed:{exc}",
                epoch=self.epoch,
                monitors=self.monitors,
                cut_cost=sum(prospective.nodes[n].monitor_cost for n in self.monitors if n in prospective.nodes),
                latency_ns=perf_counter_ns() - started,
                certificates=self.certificates,
            )

        monitors = frozenset().union(*(result.nodes for result in cuts.values()))
        union_cost = sum(prospective.nodes[name].monitor_cost for name in monitors)
        if self.monitor_budget is not None and union_cost > self.monitor_budget:
            return AdmissionDecision(
                accepted=False,
                reason="monitor_budget_exceeded",
                epoch=self.epoch,
                monitors=self.monitors,
                cut_cost=union_cost,
                latency_ns=perf_counter_ns() - started,
                certificates=self.certificates,
            )

        next_epoch = self.epoch + 1
        certificates = self._certify(prospective, cuts, next_epoch)
        self.graph = prospective
        self.epoch = next_epoch
        self.monitors = monitors
        self.certificates = certificates
        return AdmissionDecision(
            accepted=True,
            reason="admitted",
            epoch=self.epoch,
            monitors=self.monitors,
            cut_cost=union_cost,
            latency_ns=perf_counter_ns() - started,
            certificates=self.certificates,
        )

    def is_closed(self) -> bool:
        return all(
            not self.graph.has_path(
                self.graph.sources(policy), self.graph.sinks(policy), excluded=self.monitors
            )
            for policy in self.policies
        )


def verify_certificate(
    graph: InfluenceGraph,
    policy: RiskPolicy,
    certificate: ClosureCertificate,
) -> bool:
    """Independently verify binding, cut cost, and path closure."""

    if certificate.graph_digest != graph.digest() or certificate.policy != policy.name:
        return False
    monitors = frozenset(certificate.monitors)
    if any(name not in graph.nodes or not graph.nodes[name].monitorable for name in monitors):
        return False
    actual_cost = sum(graph.nodes[name].monitor_cost for name in monitors)
    if actual_cost != certificate.cut_cost:
        return False
    payload = {
        "epoch": certificate.epoch,
        "graph_digest": certificate.graph_digest,
        "policy": certificate.policy,
        "monitors": sorted(monitors),
        "cut_cost": certificate.cut_cost,
    }
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if digest != certificate.certificate_digest:
        return False
    return not graph.has_path(graph.sources(policy), graph.sinks(policy), excluded=monitors)
