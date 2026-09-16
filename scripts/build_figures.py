from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw" / "dynamic_topology_results.csv"
ANALYSIS = ROOT / "results" / "analysis" / "confirmatory_analysis.json"
MCP_ANALYSIS = ROOT / "results" / "mcp_confirmatory_v1" / "analysis" / "mcp_llm_analysis.json"
HOSTED_MCP_ANALYSIS = ROOT / "results" / "hosted_confirmatory_v3" / "analysis" / "hosted_mcp_llm_analysis.json"
FIGURES = ROOT / "paper" / "figures"
FIGURES.mkdir(parents=True, exist_ok=True)

rows = list(csv.DictReader(RAW.open(encoding="utf-8", newline="")))
analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))

method_order = ["startup-cut", "periodic-5", "sink-mediation", "full-mediation", "epochcut"]
labels = ["Startup cut", "Periodic-5", "Sink mediation", "Full mediation", "EpochCut"]
unsafe = [100 * analysis["methods"][method]["unsafe_accept_rate"] for method in method_order]
cost = [analysis["methods"][method]["mean_monitor_cost"] for method in method_order]
colors = ["#9b2226", "#ca6702", "#577590", "#264653", "#0a9396"]

fig, axes = plt.subplots(2, 1, figsize=(3.5, 4.25), sharey=True)
axes[0].barh(labels, unsafe, color=colors, height=0.65)
axes[0].set_xlabel("Unsafe accepted attacks (%)")
axes[0].set_xlim(0, 108)
axes[0].grid(axis="x", alpha=0.25)
axes[0].invert_yaxis()
for i, value in enumerate(unsafe):
    axes[0].text(value + 1.5, i, f"{value:.1f}", ha="left", va="center", fontsize=8)

axes[1].barh(labels, cost, color=colors, height=0.65)
axes[1].set_xlabel("Mean weighted monitoring cost")
axes[1].set_xlim(0, 195)
axes[1].grid(axis="x", alpha=0.25)
for i, value in enumerate(cost):
    axes[1].text(value + 2.5, i, f"{value:.1f}", ha="left", va="center", fontsize=8)
fig.tight_layout(pad=0.6)
fig.savefig(FIGURES / "security_cost.pdf", bbox_inches="tight")
fig.savefig(FIGURES / "security_cost.png", dpi=220, bbox_inches="tight")
plt.close(fig)

sizes = sorted(int(size) for size in analysis["strata"])
p50 = [analysis["strata"][str(size)]["p50_latency_ms"] for size in sizes]
p95 = [analysis["strata"][str(size)]["p95_latency_ms"] for size in sizes]
p99 = [analysis["strata"][str(size)]["p99_latency_ms"] for size in sizes]
fig, ax = plt.subplots(figsize=(3.5, 2.55))
ax.plot(sizes, p50, marker="o", label="p50", color="#0a9396")
ax.plot(sizes, p95, marker="s", label="p95", color="#ee9b00")
ax.plot(sizes, p99, marker="^", label="p99", color="#9b2226")
ax.set_xlabel("Initial agent count")
ax.set_ylabel("Admission latency (ms)")
ax.set_xticks(sizes)
ax.grid(alpha=0.25)
ax.legend(frameon=False, ncol=3, fontsize=8, loc="upper left")
fig.tight_layout()
fig.savefig(FIGURES / "latency_scaling.pdf", bbox_inches="tight")
fig.savefig(FIGURES / "latency_scaling.png", dpi=220, bbox_inches="tight")
plt.close(fig)

print(FIGURES / "security_cost.pdf")
print(FIGURES / "latency_scaling.pdf")

fig, ax = plt.subplots(figsize=(7.1, 2.75))
ax.set_xlim(0, 10)
ax.set_ylim(0, 4.2)
ax.axis("off")


def box(x: float, y: float, w: float, h: float, text: str, color: str, edge: str = "#334155") -> None:
    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.08",
        facecolor=color, edgecolor=edge, linewidth=1.1
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8)


def arrow(x1: float, y1: float, x2: float, y2: float, color: str = "#475569", style: str = "-") -> None:
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=9,
                                 linewidth=1.0, linestyle=style, color=color))


box(0.15, 2.55, 1.25, 0.62, "Untrusted\nentries", "#fee2e2", "#9b2226")
box(2.05, 2.78, 1.2, 0.62, "Agent A", "#e2e8f0")
box(3.75, 3.28, 1.2, 0.62, "Shared\nmemory", "#fef3c7")
box(3.75, 2.15, 1.2, 0.62, "Spawned\nagent", "#e2e8f0")
box(5.55, 2.78, 1.35, 0.62, "Trusted monitor", "#ccfbf1", "#0a9396")
box(7.55, 2.55, 1.55, 0.92, "Protected effects\nstate | authority\naction", "#dbeafe", "#1d4ed8")
arrow(1.4, 2.86, 2.05, 3.02)
arrow(3.25, 3.1, 3.75, 3.55)
arrow(3.25, 2.98, 3.75, 2.47)
arrow(4.95, 3.52, 5.55, 3.18)
arrow(4.95, 2.46, 5.55, 2.98)
arrow(6.9, 3.08, 7.55, 3.02)
ax.text(5.95, 3.62, "risk-specific cut", fontsize=7.5, color="#0f766e", ha="center")

box(0.45, 0.45, 1.45, 0.58, "Topology\nmutation", "#f1f5f9")
box(2.35, 0.45, 1.55, 0.58, "Prospective\ngraph", "#f1f5f9")
box(4.35, 0.45, 1.55, 0.58, "Solve + verify\nall cuts", "#ccfbf1", "#0a9396")
box(6.35, 0.45, 1.45, 0.58, "Hash-bound\ncertificate", "#f1f5f9")
box(8.25, 0.45, 1.35, 0.58, "Atomic epoch\ncommit", "#dbeafe", "#1d4ed8")
arrow(1.9, 0.74, 2.35, 0.74)
arrow(3.9, 0.74, 4.35, 0.74)
arrow(5.9, 0.74, 6.35, 0.74)
arrow(7.8, 0.74, 8.25, 0.74)
arrow(8.92, 1.03, 6.3, 2.75, color="#0a9396", style="--")
ax.text(0.2, 1.46, "Data plane", fontsize=8.5, fontweight="bold", color="#334155")
ax.text(0.2, 0.12, "EpochCut control plane", fontsize=8.5, fontweight="bold", color="#334155")
ax.plot([0.15, 9.65], [1.35, 1.35], color="#cbd5e1", linewidth=0.9)
fig.tight_layout(pad=0.2)
fig.savefig(FIGURES / "architecture.pdf", bbox_inches="tight")
fig.savefig(FIGURES / "architecture.png", dpi=220, bbox_inches="tight")
plt.close(fig)
print(FIGURES / "architecture.pdf")

if MCP_ANALYSIS.is_file() and HOSTED_MCP_ANALYSIS.is_file():
    mcp_analysis = json.loads(MCP_ANALYSIS.read_text(encoding="utf-8"))
    hosted_analysis = json.loads(HOSTED_MCP_ANALYSIS.read_text(encoding="utf-8"))
    model_names = ["qwen3:1.7b", "qwen3:8b", "gemma4:e2b"]
    model_labels = ["Qwen3\n1.7B", "Qwen3\n8B", "Gemma 4\nE2B", "N3 Super\n(hosted)"]
    width = 0.34
    native_attack = [
        100 * mcp_analysis["by_model"][name]["native"]["attack_success_rate"]
        for name in model_names
    ]
    native_attack.append(
        100 * hosted_analysis["by_model"]["nvidia-nemotron-3-super"]["native"]["attack_success_rate"]
    )
    epoch_attack = [
        100 * mcp_analysis["by_model"][name]["epochcut"]["attack_success_rate"]
        for name in model_names
    ]
    epoch_attack.append(
        100 * hosted_analysis["by_model"]["nvidia-nemotron-3-super"]["epochcut"]["attack_success_rate"]
    )
    native_benign = [
        100 * mcp_analysis["by_model"][name]["native"]["benign_correct_rate"]
        for name in model_names
    ]
    native_benign.append(
        100 * hosted_analysis["by_model"]["nvidia-nemotron-3-super"]["native"]["benign_correct_rate"]
    )
    epoch_benign = [
        100 * mcp_analysis["by_model"][name]["epochcut"]["benign_correct_rate"]
        for name in model_names
    ]
    epoch_benign.append(
        100 * hosted_analysis["by_model"]["nvidia-nemotron-3-super"]["epochcut"]["benign_correct_rate"]
    )
    x = list(range(len(model_labels)))
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.55))
    for ax, native_values, epoch_values, ylabel in (
        (axes[0], native_attack, epoch_attack, "Committed attack effects (%)"),
        (axes[1], native_benign, epoch_benign, "Exact benign completion (%)"),
    ):
        left = ax.bar([value - width / 2 for value in x], native_values, width,
                      label="Native MCP", color="#9b2226")
        right = ax.bar([value + width / 2 for value in x], epoch_values, width,
                       label="EpochCut", color="#0a9396")
        ax.set_xticks(x, model_labels)
        ax.tick_params(axis="x", labelsize=8)
        ax.set_ylim(0, 112)
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.25)
        if ax is axes[0]:
            ax.bar_label(left, fmt="%.1f", fontsize=8, padding=2)
            ax.bar_label(right, fmt="%.1f", fontsize=8, padding=2)
        else:
            for index, value in enumerate(native_values):
                ax.text(index, value + 2, f"{value:.1f} each", ha="center", fontsize=8)
    axes[0].legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout(pad=0.7)
    fig.savefig(FIGURES / "mcp_llm_security.pdf", bbox_inches="tight")
    fig.savefig(FIGURES / "mcp_llm_security.png", dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(FIGURES / "mcp_llm_security.pdf")
