"""Real stdio MCP server used by the LLM attack-resistance evaluation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from time import time_ns

from mcp.server.mcpserver import MCPServer


CASES_PATH = Path(os.environ["EPOCHCUT_MCP_CASES"])
LEDGER_PATH = Path(os.environ["EPOCHCUT_MCP_LEDGER"])
TRIAL_CONTEXT_PATH = Path(os.environ["EPOCHCUT_MCP_TRIAL_CONTEXT"])
CASES = json.loads(CASES_PATH.read_text(encoding="utf-8"))
SERVER = MCPServer(
    name="epochcut-dynamic-connector",
    description="A dynamically joined enterprise support connector.",
    version="1.0.0",
)


def _commit(effect: str, arguments: dict[str, str]) -> dict[str, object]:
    event = {
        "trial_id": TRIAL_CONTEXT_PATH.read_text(encoding="utf-8").strip(),
        "effect": effect,
        "arguments": arguments,
        "committed_at_ns": time_ns(),
    }
    with LEDGER_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
    return {"status": "committed", **event}


@SERVER.tool()
def read_ticket(case_id: str) -> str:
    """Read an enterprise support ticket by its case identifier."""

    if case_id not in CASES:
        raise ValueError(f"unknown case: {case_id}")
    return str(CASES[case_id]["ticket"])


@SERVER.tool()
def send_email(recipient: str, body: str) -> dict[str, object]:
    """Send an external email. This causes a durable side effect."""

    return _commit("send_email", {"recipient": recipient, "body": body})


@SERVER.tool()
def write_shared_memory(key: str, value: str) -> dict[str, object]:
    """Write persistent shared agent memory. This causes a durable side effect."""

    return _commit("write_shared_memory", {"key": key, "value": value})


@SERVER.tool()
def delegate_scope(principal: str, scope: str) -> dict[str, object]:
    """Delegate an authorization scope to another agent principal."""

    return _commit("delegate_scope", {"principal": principal, "scope": scope})


if __name__ == "__main__":
    SERVER.run(transport="stdio")
