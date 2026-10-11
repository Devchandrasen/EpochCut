"""Verify conceptual visual exports and native editable diagram elements."""
from hashlib import sha256
import json
from pathlib import Path
import struct

from prepare_editable_flow import flatten

ROOT = Path(__file__).resolve().parents[1]


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def verify():
    count = 0
    def check(condition, message):
        nonlocal count
        if not condition:
            raise ValueError(message)
        count += 1

    manifest = json.loads((ROOT / "docs/assets/visual-manifest.json").read_text(encoding="utf-8"))
    check(manifest["schema"] == "epochcut-conceptual-visuals/1" and manifest["kind"] == "conceptual",
          "Cover must be conceptual, not a research-result chart")
    check(file_hash(ROOT / manifest["source"]) == manifest["source_sha256"],
          "Visual source changed; regenerate the cover")
    for path, expected in manifest["outputs"].items():
        target = (ROOT / path).resolve()
        check(target.is_relative_to(ROOT), "Visual path escapes repository")
        check(target.is_file() and file_hash(target) == expected, f"Missing or changed visual: {path}")
        if target.suffix == ".png":
            header = target.read_bytes()[:24]
            check(header[:8] == b"\x89PNG\r\n\x1a\n", "Invalid PNG cover")
            width, height = struct.unpack(">II", header[16:24])
            check(width >= 1200 and height >= 500, "Undersized cover")
    for extension in ("mmd", "svg", "png", "excalidraw"):
        check((ROOT / f"diagrams/retained-authority.{extension}").is_file(),
              f"Missing protocol diagram export: {extension}")
    main_flow = (ROOT / "diagrams/retained-authority.mmd").read_text(encoding="utf-8")
    editable_flow = (ROOT / "diagrams/retained-authority-editable.mmd").read_text(encoding="utf-8")
    check(editable_flow == flatten(main_flow), "Editable conversion source is stale")
    scene = json.loads((ROOT / "diagrams/retained-authority.excalidraw").read_text(encoding="utf-8"))
    check(scene["type"] == "excalidraw" and len(scene["elements"]) > 20,
          "Diagram must contain native editable elements")
    check(not scene.get("files") and all(e["type"] != "image" for e in scene["elements"]),
          "Editable diagram cannot be a flattened background image")
    return count


if __name__ == "__main__":
    try:
        print(f"PASS: {verify()} conceptual visual and editable-diagram checks.")
    except (ValueError, OSError, KeyError) as exc:
        raise SystemExit(f"FAIL: {exc}")
