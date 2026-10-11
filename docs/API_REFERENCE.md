# API reference

The graph and topology interfaces are exported from `epochcut`. Temporal
interfaces are imported from `epochcut.temporal`. Core types have no model-provider
dependency. These interfaces are intended for prototype adapters and tests.

## Graphs

`Node(name, kind, monitor_cost=1, monitorable=True)` describes a runtime entity.
Adapters must supply positive configured costs. An unmonitorable node cannot
serve as a finite-cost enforcement location.

`Edge(source, target, interface)` describes a directed influence interface.
Both endpoints must exist before insertion.

`InfluenceGraph` supports `add_node`, `add_edge`, `apply`, `has_path` and `digest`.
Its digest uses a canonical ordering; `has_path` provides the independent
reachability check when selected enforcement nodes are excluded.

`RiskPolicy(name, source_kinds, sink_kinds)` selects source and sink node kinds
for the topology engine. `Mutation` describes prospective node and edge changes.

## Topology admission

`EpochCutEngine(graph, policies, monitor_budget=None)` manages prospective
topology changes. `propose(mutation)` returns an `AdmissionDecision`, including
acceptance, reason, epoch, monitors, configured cut cost and certificates.
`is_closed()` independently checks live path closure.

`verify_certificate(graph, policy, certificate)` checks graph and policy binding,
monitor validity, cost, certificate digest and declared path closure. It does
not use the solver's residual state as proof.

## Retained request epochs

```python
from epochcut.temporal import Broker, Policy, moving_graph

broker = Broker(*moving_graph())
try:
    # Use the executable example for the full request and cleanup sequence.
    print(broker.statistics())
finally:
    broker.close()
```

`Policy(name, sources, sinks, eligible, ...)` declares explicit node identities
for the temporal protocol. `Broker(graph, policies, strategy="epochcut", ...)`
creates the initial configuration and sandbox ledger. Control strategies other
than `epochcut`, `sink` and `full` may deliberately weaken mediation; they are
not interchangeable deployment defaults.

| Method | Behaviour |
|---|---|
| `admit(graph, policies, ...)` | Verify and activate a prospective configuration after installation acknowledgement |
| `begin(workflow, source, intent, ...)` | Issue an authenticated context bound to the current epoch and approved action |
| `advance(token, target, interface, action, sender=None)` | Validate a declared route and perform any selected enforcement check |
| `delegate(token, target, action)` | Create a scoped child on a declared delegation edge with its own identity |
| `commit(token, action)` | Validate the action grant and current authority, then record under local duplicate constraints |
| `finish(token, cancel=False)` | Release the request reference or cancel it and its active children |
| `revoke(workflow)` | Revoke current workflow authority and cancel active contexts |
| `store(key, value, provenance)` | Store non-authoritative content and provenance |
| `reenter_memory(key, workflow, source, intent)` | Read stored content through a fresh request context |
| `effects()` / `statistics()` | Inspect local records and retained-state counts |
| `close()` | Close the ledger connection |

`solve`, `make_certificate` and `verify_v2` expose temporal placement and
certificate construction/verification. `moving_graph()` supplies the small
example graph. See [temporal_quickstart.py](../examples/temporal_quickstart.py)
for an executable route, update, denial and cleanup sequence.

## Intent gate and adapters

`epochcut.mcp_policy.IntentManifest` declares denied effects or an allowed tool
with exact required arguments. `authorize_effect` checks a proposal;
`SingleUseIntentGate.authorize` additionally consumes a matching protected intent
and rejects reuse. This gate is separate from the temporal broker.

The [MCP connector](../evaluation/mcp_dynamic_server.py) is an optional stdio
sandbox. It expects caller-supplied case, ledger and trial-context paths in
`EPOCHCUT_MCP_CASES`, `EPOCHCUT_MCP_LEDGER` and `EPOCHCUT_MCP_TRIAL_CONTEXT`.
Its tool names simulate effects by writing local records; the connector alone
is not an enforcement gate. Install optional dependencies with
`python -m pip install -e ".[mcp-eval]"` if using it.

`epochcut.network` contains authenticated loopback HTTP prototype services.
They use generated test credentials supplied through `EPOCHCUT_TEST_KEYS` and
are not remote production endpoints. Do not expose them on an external interface.
