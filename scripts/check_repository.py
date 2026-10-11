"""Enforce the public code/documentation boundary and check local Markdown links."""
import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {".gitattributes", ".gitignore", "README.md", "CITATION.cff", "SECURITY.md",
              "pyproject.toml", "requirements-visuals.txt"}
DIRECTORIES = {"src", "tests", "examples", "evaluation", "scripts", "docs", "diagrams", ".github"}
PRIVATE_PARTS = {"paper", "submission", "results", "audit", "output", "tmp", "private-backups"}
PRIVATE_EXTENSIONS = {".pdf", ".tex", ".bib", ".doc", ".docx", ".zip", ".7z", ".rar",
                      ".jsonl", ".csv", ".key", ".pem"}
SECRET_PATTERN = re.compile(rb'(?:nvapi-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,}|'
                            rb'sk-[A-Za-z0-9_-]{25,}|AQ\.[A-Za-z0-9_-]{25,}|'
                            rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def tracked_files(staged=False, archive=False):
    if archive:
        return sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*")
                      if p.is_file() and "__pycache__" not in p.parts
                      and ".pytest_cache" not in p.parts and p.suffix != ".pyc")
    completed = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                               check=True, capture_output=True)
    return sorted(p.decode("utf-8") for p in completed.stdout.split(b"\0") if p)


def file_bytes(name, staged=False):
    if staged:
        return subprocess.run(["git", "-C", str(ROOT), "show", ":"+name],
                              check=True, capture_output=True).stdout
    return (ROOT / name).read_bytes()


def validate_paths(names):
    for name in names:
        path = PurePosixPath(name)
        lowered = tuple(p.lower() for p in path.parts)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Unsafe tracked path: {name}")
        if (path.suffix.lower() in PRIVATE_EXTENSIONS
                or any(p in PRIVATE_PARTS or p.startswith("paper_") for p in lowered)
                or path.name.startswith(".env")):
            raise ValueError(f"Private/publication/archive file cannot be published: {name}")
        if not (name in ROOT_FILES or path.parts[0] in DIRECTORIES and len(path.parts) > 1):
            raise ValueError(f"File is outside code/documentation scope: {name}")


def verify(staged=False, archive=False):
    names = tracked_files(staged, archive)
    if not names:
        raise ValueError("No repository files found")
    validate_paths(names)
    contents = {name: file_bytes(name, staged) for name in names}
    for name, content in contents.items():
        if SECRET_PATTERN.search(content):
            raise ValueError(f"Potential credential in {name}; value withheld")
    links_checked = 0
    for name, content in contents.items():
        if not name.endswith(".md"):
            continue
        source = content.decode("utf-8")
        links = re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', source)
        links += re.findall(r'(?:src|href)="([^"]+)"', source)
        for link in links:
            parsed = urlsplit(link.strip("<>"))
            if parsed.scheme or parsed.netloc:
                continue
            target = ((ROOT / name).parent / unquote(parsed.path)).resolve() if parsed.path else ROOT / name
            if not target.is_relative_to(ROOT):
                raise ValueError(f"Link escapes repository: {name}: {link}")
            relative = target.relative_to(ROOT).as_posix()
            exists = relative in contents or any(p.startswith(relative.rstrip("/")+"/") for p in names)
            if not exists:
                raise ValueError(f"Broken local link: {name}: {link}")
            if parsed.fragment and relative.endswith(".md"):
                headings = re.findall(r'^#{1,6} (.+)$', contents[relative].decode("utf-8"), re.M)
                slugs = {re.sub(r'[^\w\- ]', '', h.lower()).replace(' ', '-') for h in headings}
                if unquote(parsed.fragment) not in slugs:
                    raise ValueError(f"Broken heading link: {name}: {link}")
            links_checked += 1
    return len(names), links_checked


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--staged", action="store_true", help="Read actual staged blobs instead of working files")
    group.add_argument("--archive", action="store_true", help="Check a fresh-extracted code-only archive")
    args = parser.parse_args()
    try:
        files, links = verify(args.staged, args.archive)
        print(f"PASS: {files} files within code/documentation scope; {links} local links; credential-pattern check.")
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"FAIL: {exc}")
