# Architecture

EpochCut models declared influence routes rather than the meaning of generated
text. Its control plane verifies an enforcement placement before activation;
its temporal broker keeps pending work attached to the placement that admitted it.

![Admission, retained request lifetime and local recording](../diagrams/retained-authority.png)

## Graph and placement

An `InfluenceGraph` contains typed nodes and directed, interface-labelled edges.
A policy specifies influence sources, protected effects and eligible enforcement
locations. Node splitting and max-flow select a minimum-cost eligible vertex cut.

A separate reachability check verifies that removing the selected locations
closes every declared source-to-effect path. The certificate binds the graph,
policy, epoch, placement and configured costs. Policies are solved separately;
the union of their cuts is not a joint multi-policy optimum.

## Two entry points

`EpochCutEngine` copies the live graph, applies a proposed mutation to the copy,
solves and verifies the resulting placement, then commits atomically. A rejected
mutation leaves the live graph unchanged.

`epochcut.temporal.Broker` adds authenticated request contexts, installation
acknowledgement, retained configurations, scoped children and a local effect
ledger. A request uses the epoch that admitted it even if a new epoch becomes
active while the request waits in a queue.

## Request lifetime

Context authority comes from the trusted broker, not fields supplied inside an
agent payload. Each context binds its request identity, workflow, admitted epoch,
policy digest, expiry and action scope. A delegated child has a new request
identity and cannot widen its parent's approved action. Reading stored content
starts a fresh context rather than reusing the writer's authority.

Old configurations remain available while active requests reference them. They
retire only after those references are released. Retention preserves the
enforcement configuration, not permission after cancellation or revocation.

## Local effect ordering

The selected enforcement point compares the complete proposed action with the
approved intent and issues an action-bound grant. At the local recording
boundary, the broker checks the matching grant, current authority, expiry and
duplicate constraints under a lock and SQLite transaction.

This ordering covers local records only. Adapters for external delivery or
distributed effects need their own idempotency and failure-handling design.

## Trust boundary

Trusted components include approval input, authenticated control, the verifier,
installed enforcement points and the effect broker. Agent text, stored content,
claimed context fields and computational principals are non-authoritative.

The prototype assumes complete reporting of security-relevant routes and an
effect boundary that cannot be bypassed. It does not detect hidden interfaces,
classify prompt injection or certify an arbitrary production deployment.
Loopback HTTP services and the MCP connector use sandbox effects, not real email
or identity services.

Follow the [temporal example](TEMPORAL_PROTOCOL.md) for a concrete moving-cut
case, and the [API reference](API_REFERENCE.md) for implementation entry points.
