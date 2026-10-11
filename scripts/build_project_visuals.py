"""Export a conceptual project cover without reading any research dataset."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/assets"


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

    OUTPUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none",
                         "svg.hashsalt": "epochcut-code-documentation"})
    fig = plt.figure(figsize=(14, 6.2), facecolor="#10283d")
    ax = fig.add_axes([0, 0, 1, 1], xlim=(0, 1400), ylim=(0, 620))
    ax.axis("off")
    ax.text(62, 555, "RETAINED AUTHORITY  /  AGENT RUNTIMES", color="#79d7ca", fontsize=11, weight="bold")
    ax.text(58, 500, "EpochCut", color="white", fontsize=53, weight="bold", va="top")
    ax.text(63, 400, "Enforcement can move.\nAction approval stays bound.", color="#dbe7ef", fontsize=20,
            linespacing=1.5, va="top")
    ax.text(63, 285, "Verified placement  ·  Retained epochs\nExact action grants  ·  Current authority",
            color="#a7c0d3", fontsize=13, linespacing=1.7, va="top")
    ax.text(63, 209, "Code  |  Documentation  |  Local examples", color="#79d7ca", fontsize=10)

    ax.add_patch(FancyBboxPatch((720, 190), 615, 350, boxstyle="round,pad=0,rounding_size=18",
                              facecolor="#18354c", edgecolor="#36556b"))
    ax.text(751, 508, "One request. Two enforcement epochs.", color="white", fontsize=15, weight="bold")
    positions = [775, 895, 1015, 1135, 1255]
    for y, selected, title in ((411, "c", "Epoch 0: pending work"), (280, "a", "Epoch 1: new admissions")):
        ax.text(750, y+48, title, color="#a7c0d3", fontsize=11)
        for start, end in zip(positions[:-1], positions[1:]):
            ax.add_patch(FancyArrowPatch((start+23, y), (end-24, y), arrowstyle="-|>",
                                        mutation_scale=12, color="#9bb2c6", linewidth=1.4))
        for x, label in zip(positions, ("s", "a", "b", "c", "t")):
            colour = "#79d7ca" if label == selected else "#b8c8d5"
            ax.add_patch(Circle((x, y), 23, facecolor="#18354c", edgecolor=colour, linewidth=2))
            if label == selected:
                ax.add_patch(Circle((x, y), 29, fill=False, edgecolor=colour, linewidth=2))
            ax.text(x, y, label, color="white", fontsize=16, ha="center", va="center", weight="bold")
    ax.add_patch(FancyArrowPatch((795, 423), (995, 423), connectionstyle="arc3,rad=-.33",
                                arrowstyle="-|>", mutation_scale=12, color="#9bb2c6", linewidth=1.3))
    ax.text(1015, 351, "queued q keeps epoch 0", color="#f4c679", fontsize=10, ha="center", weight="bold")
    ax.text(751, 214, "Double border: selected enforcement point", color="#79d7ca", fontsize=10)

    cards = [("VERIFY", "Declared path closure"), ("RETAIN", "Pending request epochs"),
             ("BIND", "Complete approved actions"), ("CHECK", "Current authority at recording")]
    for index, (title, label) in enumerate(cards):
        x = 62+325*index
        ax.add_patch(FancyBboxPatch((x, 59), 300, 112, boxstyle="round,pad=0,rounding_size=10",
                                  facecolor="#1b3a51", edgecolor="#36556b"))
        ax.text(x+20, 127, title, color="white", fontsize=22, weight="bold")
        ax.text(x+20, 88, label, color="#b8cbd9", fontsize=10)
    ax.text(63, 23, "Conceptual implementation diagram. Prototype sandbox effects; no measured benchmark scores.",
            color="#90a9bc", fontsize=9)
    outputs = {}
    for extension in ("png", "svg"):
        target = OUTPUT / f"epochcut-cover.{extension}"
        metadata = {"Software": "EpochCut project visuals"} if extension == "png" else {"Date": None}
        fig.savefig(target, dpi=150, facecolor=fig.get_facecolor(), metadata=metadata)
        if extension == "svg":
            text = "\n".join(line.rstrip() for line in target.read_text(encoding="utf-8").splitlines())+"\n"
            target.write_text(text, encoding="utf-8", newline="\n")
        outputs[target.relative_to(ROOT).as_posix()] = file_hash(target)
    plt.close(fig)
    manifest = {"schema": "epochcut-conceptual-visuals/1", "kind": "conceptual",
                "source": "scripts/build_project_visuals.py",
                "source_sha256": file_hash(Path(__file__)), "outputs": outputs}
    (OUTPUT / "visual-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n",
                                                encoding="utf-8", newline="\n")
    print("Exported conceptual cover: PNG, SVG and source/export hashes. No dataset read.")


if __name__ == "__main__":
    main()
