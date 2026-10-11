# Getting started

The core implementation uses the Python standard library. The examples below
do not contact a model provider, open a remote service or send real messages.

## Set up an environment

Python 3.11 or newer is required.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Try topology admission

```bash
python examples/quickstart.py
```

The example admits a guarded plugin route, rejects an unmonitorable bypass,
and checks that a rejected mutation leaves the live graph closed.

## Try retained request epochs

```bash
python examples/temporal_quickstart.py
```

The example queues requests before an enforcement point, admits a new placement,
and resumes the pending work under its retained epoch. An approved action is
recorded once in an in-memory ledger. A substituted action is denied. The old
epoch retires when its last active request finishes.

## Run checks

```bash
python -m pytest -q
python scripts/check_repository.py
python scripts/verify_project_showcase.py
```

Tests check implementation behaviour. Repository checks reject publication
files, recorded-result archives, credentials and broken local documentation
links. Visual checks verify the conceptual cover and editable diagram exports.

Next, read [Architecture](ARCHITECTURE.md), the [API reference](API_REFERENCE.md),
or the [development guide](DEVELOPMENT.md).
