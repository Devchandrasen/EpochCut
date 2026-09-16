# API reference

The stable public surface for version 0.1 is exported from `epochcut`.

## Graph types

### `Node(name, kind, monitor_cost=1, monitorable=True)`

Defines a security-relevant runtime entity. `monitor_cost` must be treated as a
positive integer by adapters; `monitorable=False` gives the node infinite cut
capacity.

### `Edge(source, target, interface)`

Defines a directed influence interface. Both endpoints must exist before the
edge is added.

### `InfluenceGraph`

- `add_node(node)` adds an idempotent node and rejects conflicting redefinition.
- `add_edge(edge)` requires known endpoints.
- `apply(mutation)` removes requested edges, adds nodes, then adds edges.
- `sources(policy)` and `sinks(policy)` select nodes by kind.
- `has_path(sources, sinks, excluded=())` performs the independent reachability check.
- `digest()` returns SHA-256 over a canonical, deterministically ordered graph.

### `RiskPolicy(name, source_kinds, sink_kinds)`

Declares which node kinds begin and end a protected influence path.

### `Mutation(mutation_id, add_nodes=(), add_edges=(), remove_edges=(), adversarial=False)`

Describes one prospective graph transaction. `adversarial` is experimental
metadata; admission depends on the resulting graph rather than that label.

## Admission and certificates

### `EpochCutEngine(graph, policies, monitor_budget=None)`

Initializes a fail-closed epoch manager from a copy of the supplied graph.

- `propose(mutation) -> AdmissionDecision` solves and verifies a prospective
  graph, checks the optional union monitor budget, and commits atomically only
  when every policy remains closed.
- `is_closed() -> bool` independently checks the live graph against the active
  union of monitors.

### `AdmissionDecision`

Immutable fields: `accepted`, `reason`, `epoch`, `monitors`, `cut_cost`,
`latency_ns`, and `certificates`. Rejected decisions preserve the current live
epoch and monitor set.

### `ClosureCertificate`

Immutable fields: `epoch`, `graph_digest`, `policy`, `monitors`, `cut_cost`,
and `certificate_digest`.

### `verify_certificate(graph, policy, certificate) -> bool`

Checks graph and policy binding, monitor validity, cost, certificate digest,
and source-to-sink path closure. It does not trust the solver's internal state.

## MCP intent gate

### `IntentManifest`

- `IntentManifest.deny_effects(case_id)` authorizes no protected effect.
- `IntentManifest.allow_effect(case_id, tool, required_arguments)` authorizes
  one protected tool with exact string-matched required arguments.

### `authorize_effect(manifest, tool, arguments) -> PolicyDecision`

Checks a proposed effect against explicit user intent. Current protected tool
identifiers are `send_email`, `write_shared_memory`, and `delegate_scope`.
Unprotected tools return `not_protected`.

### `SingleUseIntentGate(manifest)`

`authorize(tool, arguments)` consumes the first matching protected effect and
rejects a replay with `intent_already_consumed`.

## Research commands

| Command | Purpose |
|---|---|
| `scripts/run_experiments.py --protocol PATH` | Run the frozen dynamic-graph benchmark |
| `scripts/analyse_results.py --raw CSV --protocol PATH` | Compute graph metrics, intervals, and claim gates |
| `scripts/run_mcp_llm_evaluation.py --output-dir DIR [options]` | Run local LLM/MCP trials |
| `scripts/run_hosted_mcp_llm_evaluation_v3.py --protocol PATH --output-dir DIR [options]` | Run the hosted provider extension |
| `scripts/analyse_mcp_llm.py --raw CSV --protocol JSON --ledger JSONL --transcripts JSONL --output JSON` | Validate MCP records and compute gate outcomes |
| `scripts/build_figures.py` | Regenerate manuscript figures from archived analyses |
| `scripts/verify_artifacts.py` | Verify required files, digests, and frozen gate patterns |

All paths are interpreted relative to the current working directory unless an
absolute path is supplied.
