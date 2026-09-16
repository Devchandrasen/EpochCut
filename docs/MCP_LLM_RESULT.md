# Confirmatory MCP and Real-LLM Result

Status: **all seven frozen claim gates passed**.

## Main result

- 126/126 agent trials completed without an error.
- Native MCP committed 18/45 injected durable effects (40.0%, Wilson 95% CI
  27.02% to 54.55%).
- EpochCut committed 0/45 injected effects (Wilson 95% upper bound 7.87%).
- The three guarded models attempted 18 attacks; EpochCut blocked 18/18.
- Exact benign completion was 16/18 (88.9%) in both native and EpochCut modes.
- Source reading completed in 126/126 trials.
- Intent-gateway latency was 0.0047 ms at p50 and 0.0096 ms at p95.
- Fifty successful effect calls in the trial CSV reconcile exactly with fifty
  events in the persistent MCP ledger.

## Model strata

| Model | Native injected commits | EpochCut injected commits | Exact benign native / EpochCut |
|---|---:|---:|---:|
| Qwen3 1.7B | 6/15 | 0/15 | 4/6 / 4/6 |
| Qwen3 8B | 12/15 | 0/15 | 6/6 / 6/6 |
| Gemma4 E2B | 0/15 | 0/15 | 6/6 / 6/6 |

Gemma4 E2B's refusal is preserved as a genuine model-level result. The
security conclusion does not depend on it: the other two models generated 18
unauthorised effect calls, and none passed the EpochCut gateway.

## Evidence hashes

- Frozen protocol: `a575a04c326ec2a6a38aa8d1782265f91b8f4c8219fa502fa0e1c18887b42908`
- Trial CSV: `c7a30fab55f1a12fa932c9e75a365d4af5df054ccc6d454a34305f4a404fa9bf`
- Full transcripts: `86918a8192cac7b238043f34d9e92790f068077634aa9c2e4b08506ac4425ae0`
- Durable effect ledger: `23d3f4f676d82b008a09575979b1bc860dabe8f2096fad8bde100ff48cdcf1d8`

## Claim boundary

This is direct evidence from actual LLM inference, real MCP discovery and
dispatch, server-side tool execution, and persistent effect recording. The
effect services were sandboxed locally, and the corpus used three local models
on one host. The result therefore supports the tested MCP deployment, not a
universal or independently audited production-security claim.

