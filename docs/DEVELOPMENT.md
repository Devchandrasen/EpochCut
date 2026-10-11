# Development

The public repository contains code, documentation and conceptual project
diagrams. Keep publication material and recorded research datasets in a separate
private workspace. Do not add PDFs, LaTeX, submission packages, transcripts,
result archives or credentials here.

## Test a change

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python examples/quickstart.py
python examples/temporal_quickstart.py
python scripts/check_repository.py
python scripts/verify_project_showcase.py
```

The tests cover graph mutation, solver behaviour, certificate binding, intent
matching, context authentication, retained routing, delegation, memory re-entry,
revocation, expiry, concurrent duplicate rejection and restart behaviour.
These are implementation checks, not published experimental results.

Before committing, stage only the intended code and documentation. Then run
`python scripts/check_repository.py --staged` to inspect the actual index.
CI runs the same repository-scope checks on the committed tree.

## Edit the documentation

Use relative links inside repository Markdown. Explain the prototype's actual
interfaces and limitations. Conceptual diagrams may illustrate behaviour but
should not carry untraceable benchmark scores. See [Visuals](VISUALS.md) for
source and export paths.

## Make a code-only archive

After committing the intended files, use PowerShell:

```powershell
./scripts/package_repository.ps1 -ArchiveName EpochCut_Code_Documentation.zip
```

The script first checks the repository scope, packages tracked files only,
fresh-extracts the archive, and reruns tests, examples and documentation checks.
It does not package ignored local files or private folders. A new archive name
is required if the requested output already exists, so an older archive is not
silently overwritten.

## Security-sensitive changes

Changes to context identity, route validation, grant construction, revocation
or ledger ordering need focused tests. Avoid exposing prototype HTTP services
outside loopback. Follow the [security policy](../SECURITY.md) for private reports.
