# Frozen Research Protocol v1.0

Date frozen: 15 September 2026

## Research question

Can a multi-agent runtime admit dynamic membership and topology changes while
maintaining a machine-checkable guarantee that every declared path from an
untrusted entry point to a protected effect crosses a trusted monitor?

## Hypotheses and claim gates

The primary hypothesis is that transactional recomputation and verification of
a weighted vertex cut will yield zero unsafe accepted adversarial mutations in
the controlled graph model.  The positive claim is permitted only if all four
predeclared gates in `configs/protocol.json` pass:

1. zero unsafe accepted adversarial mutations;
2. at least 99% acceptance of benign mutations;
3. at least 50% lower mean monitoring cost than full mediation; and
4. no more than 25 ms p95 admission latency on the evaluation host.

Failure of any gate must remain in the record.  It may motivate a new protocol
version, but results from different versions must not be pooled.

## Independent variables

- Initial agents: 8, 16, 32, 64.
- Topology: chain, ring, star, tree, random directed graph.
- Twenty fixed random seeds.
- Thirty online mutations per scenario.
- Mutation families: untrusted tool return, recursive spawn, shared memory,
  delegated effect, and communication reroute.
- Adversarial and benign mutations alternate, producing balanced strata.

This yields 400 scenarios, 12,000 topology transitions, and 60,000 method-level
observations across five defenses.

## Baselines

- Startup cut: compute once before any online change.
- Periodic-5: refresh every fifth mutation.
- Sink mediation: mediate every declared protected effect.
- Full mediation: mediate every monitorable graph node.
- EpochCut: recompute, verify, certify, and atomically commit on every mutation.

## Outcomes

Primary: unsafe accepted adversarial mutation rate.

Secondary: closure rate over all transitions, benign mutation acceptance,
monitor count and weighted monitoring cost, and EpochCut admission latency.

## Threat model and assumptions

An adversary may control any untrusted source and any unmonitored agent, tool
return, memory, or communication edge.  The graph manager, monitor code, policy
definitions, and hash primitive are trusted.  Adapters must report every
security-relevant entry, interface, and effect before activation.  EpochCut
does not discover omitted edges and does not interpret malicious language.

## Statistical plan

The primary result is an exact proportion with a two-sided 95% Wilson interval.
Paired method comparisons use per-scenario rates and a paired bootstrap over
scenarios (10,000 resamples, fixed seed 20260915).  Latency is reported with
median, p95, and p99, stratified by initial size.  Because the main guarantee is
mechanistic and the corpus is generated, effect sizes and confidence intervals
are emphasized over null-hypothesis significance tests.

