"""Regression tests for the public code/documentation boundary."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_repository import validate_paths


class RepositoryScopeTests(unittest.TestCase):
    def test_code_documentation_and_native_visuals_are_allowed(self):
        validate_paths(["src/epochcut/temporal.py", "tests/test_temporal.py",
                        "docs/ARCHITECTURE.md", "diagrams/retained-authority.excalidraw",
                        "docs/assets/epochcut-cover.png", "README.md"])

    def test_publication_files_and_archives_are_rejected(self):
        for name in ("paper/main.pdf", "paper_jisa/main.tex", "docs/draft.pdf",
                     "submission/cover.md", "results/summary.json", "docs/log.csv",
                     "docs/transcripts.jsonl", "output/package.zip", "README_JISA.md"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_paths([name])

    def test_credentials_and_path_escape_are_rejected(self):
        for name in (".env", "docs/.env.local", "src/client.key", "../private/file.py"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_paths([name])


if __name__ == "__main__":
    unittest.main()
