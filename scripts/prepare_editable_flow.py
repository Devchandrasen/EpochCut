"""Prepare an ungrouped Mermaid flow for a native Excalidraw conversion."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def flatten(source):
    replacements = {"control --> lifetime": "E --> R",
                    "lifetime --> effect": "A --> C"}
    result = []
    for line in source.splitlines():
        stripped = line.strip()
        if (not stripped or stripped.startswith(("%%", "subgraph ", "direction ", "classDef ", "class "))
                or stripped == "end"):
            continue
        result.append(replacements.get(stripped, stripped))
    return "\n".join(result)+"\n"


if __name__ == "__main__":
    source = (ROOT / "diagrams/retained-authority.mmd").read_text(encoding="utf-8")
    target = ROOT / "diagrams/retained-authority-editable.mmd"
    target.write_text(flatten(source), encoding="utf-8", newline="\n")
    print("Prepared converter-compatible source:", target.relative_to(ROOT))
