from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
required = [
    ROOT / "configs" / "protocol.json",
    ROOT / "configs" / "mcp_llm_protocol.json",
    ROOT / "results" / "raw" / "dynamic_topology_results.csv",
    ROOT / "results" / "analysis" / "confirmatory_analysis.json",
    ROOT / "results" / "mcp_confirmatory_v1" / "raw" / "mcp_llm_trials.csv",
    ROOT / "results" / "mcp_confirmatory_v1" / "raw" / "mcp_llm_transcripts.jsonl",
    ROOT / "results" / "mcp_confirmatory_v1" / "raw" / "mcp_effect_ledger.jsonl",
    ROOT / "results" / "mcp_confirmatory_v1" / "raw" / "epochcut_mcp_admission.json",
    ROOT / "results" / "mcp_confirmatory_v1" / "analysis" / "mcp_llm_analysis.json",
    ROOT / "configs" / "hosted_mcp_protocol_v3.json",
    ROOT / "results" / "hosted_confirmatory_v3" / "hosted_mcp_llm_trials.csv",
    ROOT / "results" / "hosted_confirmatory_v3" / "hosted_mcp_llm_transcripts.jsonl",
    ROOT / "results" / "hosted_confirmatory_v3" / "mcp_effect_ledger.jsonl",
    ROOT / "results" / "hosted_confirmatory_v3" / "epochcut_mcp_admission.json",
    ROOT / "results" / "hosted_confirmatory_v3" / "analysis" / "hosted_mcp_llm_analysis.json",
    ROOT / "paper" / "figures" / "security_cost.pdf",
    ROOT / "paper" / "figures" / "latency_scaling.pdf",
    ROOT / "paper" / "figures" / "architecture.pdf",
    ROOT / "paper" / "figures" / "mcp_llm_security.pdf",
    ROOT / "paper" / "main.pdf",
]
missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
if missing:
    raise SystemExit("missing artifacts: " + ", ".join(missing))

graph_raw_path = ROOT / "results" / "raw" / "dynamic_topology_results.csv"
graph_analysis_path = ROOT / "results" / "analysis" / "confirmatory_analysis.json"
analysis = json.loads(graph_analysis_path.read_text(encoding="utf-8"))
raw_digest = hashlib.sha256(graph_raw_path.read_bytes()).hexdigest()
if raw_digest != analysis["raw_sha256"]:
    raise SystemExit("raw result digest mismatch")
if not analysis["all_claim_gates_pass"]:
    raise SystemExit("one or more frozen claim gates failed")

mcp_analysis_path = ROOT / "results" / "mcp_confirmatory_v1" / "analysis" / "mcp_llm_analysis.json"
mcp_raw_path = ROOT / "results" / "mcp_confirmatory_v1" / "raw" / "mcp_llm_trials.csv"
mcp_analysis = json.loads(mcp_analysis_path.read_text(encoding="utf-8"))
if hashlib.sha256(mcp_raw_path.read_bytes()).hexdigest() != mcp_analysis["digests"]["raw_sha256"]:
    raise SystemExit("MCP raw result digest mismatch")
if not mcp_analysis["all_claim_gates_pass"]:
    raise SystemExit("one or more frozen MCP claim gates failed")

hosted_analysis_path = (
    ROOT / "results" / "hosted_confirmatory_v3" / "analysis" / "hosted_mcp_llm_analysis.json"
)
hosted_raw_path = ROOT / "results" / "hosted_confirmatory_v3" / "hosted_mcp_llm_trials.csv"
hosted_analysis = json.loads(hosted_analysis_path.read_text(encoding="utf-8"))
if hashlib.sha256(hosted_raw_path.read_bytes()).hexdigest() != hosted_analysis["digests"]["raw_sha256"]:
    raise SystemExit("hosted MCP raw result digest mismatch")
expected_hosted_gates = {
    "all_attempts_blocked": True,
    "benign_correct": True,
    "guard_latency": True,
    "native_attack_opportunity": False,
    "no_errors": True,
    "source_read": True,
    "zero_epochcut_attack_commits": True,
}
if hosted_analysis["claim_gates"] != expected_hosted_gates:
    raise SystemExit("hosted MCP gate pattern differs from the reported bounded result")

manifest = {
    str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in required
}
(ROOT / "results" / "analysis" / "MANIFEST.sha256.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
)
print(json.dumps({"status": "PASS", "files": len(required)}, sort_keys=True))
