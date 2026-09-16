# Getting started

This tutorial builds a small dynamic agent graph, admits one guarded topology
change, and rejects a direct unmonitorable bypass.

## 1. Create an environment

EpochCut requires Python 3.11 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

For macOS or Linux, replace the activation command with
`source .venv/bin/activate`.

## 2. Run the walkthrough

```powershell
python examples/quickstart.py
```

The JSON output records four facts:

- the initial graph has a valid hash-bound closure certificate;
- a plugin path is admitted only after an additional guard becomes part of
  the minimum cut;
- a direct untrusted-to-effect edge is rejected because no finite monitorable
  cut exists; and
- the live graph remains closed because a rejected mutation is never committed.

## 3. Run the tests

```powershell
python -m pytest -q
```

The tests cover graph mutation, deterministic cut computation, transactional
admission, certificate verification, monitor-budget rejection, explicit MCP
intent matching, and single-use replay protection.

## 4. Verify the frozen evidence

```powershell
python scripts/verify_artifacts.py
```

Expected terminal output:

```json
{"files": 20, "status": "PASS"}
```

This command checks the presence and SHA-256 binding of the raw graph, local
MCP, hosted MCP, figure, and paper artifacts. It also checks the exact frozen
claim-gate pattern, including the hosted study's failed opportunity gate.

## Next steps

- Use the [API reference](API_REFERENCE.md) to build a graph adapter.
- Read [Architecture](ARCHITECTURE.md) before changing the trust boundary.
- Follow [Reproducing results](REPRODUCING_RESULTS.md) for full experiments.
