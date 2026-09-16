# Reproducing results

EpochCut separates deterministic artifact verification from expensive or
provider-dependent reruns. Start with the level that matches your goal.

## Level 1: implementation and archived-evidence checks

These commands need only Python 3.11+ and the development extra:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python examples/quickstart.py
python scripts/verify_artifacts.py
```

`verify_artifacts.py` recomputes digests and validates the frozen gate pattern;
it does not rerun an LLM.

## Level 2: dynamic graph experiment

The graph experiment is deterministic under the frozen protocol.

```powershell
python scripts/run_experiments.py --protocol configs/protocol.json
python scripts/analyse_results.py `
  --raw results/raw/dynamic_topology_results.csv `
  --protocol configs/protocol.json
python scripts/build_figures.py
python scripts/verify_artifacts.py
```

The experiment evaluates five strategies over 400 scenario pairs and 12,000
mutations per strategy. The primary EpochCut claim is 0/6,000 unsafe accepts
under the specified adversarial mutations.

## Level 3: local MCP + local LLM evaluation

Install the pinned MCP dependencies and provide the local models named by the
frozen protocol through Ollama:

```powershell
python -m pip install -e ".[dev,mcp-eval]"
python scripts/run_mcp_llm_evaluation.py `
  --protocol configs/mcp_llm_protocol.json `
  --output-dir results/reproduction/mcp_run
python scripts/analyse_mcp_llm.py `
  --raw results/reproduction/mcp_run/mcp_llm_trials.csv `
  --protocol configs/mcp_llm_protocol.json `
  --ledger results/reproduction/mcp_run/mcp_effect_ledger.jsonl `
  --transcripts results/reproduction/mcp_run/mcp_llm_transcripts.jsonl `
  --output results/reproduction/mcp_analysis.json
```

Use `--resume` only for the same output directory and frozen protocol. Never
replace `results/mcp_confirmatory_v1/`; it is the archived confirmatory run.

## Level 4: hosted MCP extension

The hosted runner can consume quota or paid tokens. It reads
`NVIDIA_API_KEY` from the environment or prompts interactively and does not
persist the key.

```powershell
$env:NVIDIA_API_KEY = Read-Host -MaskInput "NVIDIA API key"
python scripts/run_hosted_mcp_llm_evaluation_v3.py `
  --protocol configs/hosted_mcp_protocol_v3.json `
  --output-dir results/reproduction/hosted_mcp_run
python scripts/analyse_mcp_llm.py `
  --raw results/reproduction/hosted_mcp_run/hosted_mcp_llm_trials.csv `
  --protocol configs/hosted_mcp_protocol_v3.json `
  --ledger results/reproduction/hosted_mcp_run/mcp_effect_ledger.jsonl `
  --transcripts results/reproduction/hosted_mcp_run/hosted_mcp_llm_transcripts.jsonl `
  --output results/reproduction/hosted_mcp_analysis.json
Remove-Item Env:NVIDIA_API_KEY
```

Provider behavior can drift. Compare a new run to the frozen v3 protocol and
report its gate pattern independently; do not pool it with the archived local
study. The archived hosted run blocked every observed attack attempt, but its
native-opportunity gate failed because only three, not five, attempts occurred.

## Build the manuscript

The paper requires an IEEEtran-compatible LaTeX installation, BibTeX, and the
prebuilt figures.

```powershell
Push-Location paper
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
Pop-Location
python scripts/verify_artifacts.py
```

## Build release archives

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package_release.ps1
powershell -ExecutionPolicy Bypass -File scripts/package_repository.ps1
```

Both packaging scripts use fresh staging directories under `tmp/`; the
repository packager reruns tests and evidence verification after extraction.
