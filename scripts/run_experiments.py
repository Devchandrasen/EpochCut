from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from epochcut.benchmark import run_protocol  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    raw, summary = run_protocol(args.protocol.resolve())
    print(raw)
    print(summary)


if __name__ == "__main__":
    main()

