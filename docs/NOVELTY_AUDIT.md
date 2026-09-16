# Novelty Audit

Audit date: 15 September 2026

## Candidate directions rejected

- Prompt-injection detection or sanitization: already represented by
  AgentDojo defenses, CaMeL/Fides-style information-flow control, and recent
  token-level sanitizers.
- Static capability and delegation controls: directly adjacent to recent
  agent-principal-chain and attribute-based access-control work.
- Commit-time freshness: directly adjacent to CommitGuard.
- Memory provenance and repair: directly adjacent to MemLineage, TMA-NM, and
  MemSecBench.
- Semantic transactions and rollback: directly adjacent to Cordon and CoAgent.
- MCP manifest signing and admission: directly adjacent to ETDI, MCPSec, and
  attested server-admission proposals.
- Diverse validator quorums: directly adjacent to Semantic Quorum Assurance.

## Retained gap

The September 2026 multi-agent security systematization reports that almost all
evaluations assume fixed membership, that agreement can lose independence, and
that a local defense does not establish closure of every end-to-end attack
path.  EpochCut addresses one bounded part of that gap: online membership and
topology mutations must not become visible until a risk-specific enforcement
cut has been recomputed and verified on the prospective graph.

## Novelty boundary

EpochCut is not a language-level detector and does not replace IFC, capability
systems, or sink authorization.  It is a control-plane mechanism for deciding
where those trusted enforcement functions must be placed, and for proving that
their placement still intersects every declared source-to-effect path after a
dynamic graph change.

