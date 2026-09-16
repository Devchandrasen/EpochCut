"""Policy adapter for guarded MCP effect dispatch.

The adapter does not classify natural language.  It compares a proposed MCP
effect call with an explicit intent manifest derived from the user task.  The
EpochCut graph certificate establishes that protected calls are routed through
this adapter after a dynamic server is admitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns
from typing import Any


PROTECTED_EFFECTS = frozenset(
    {"send_email", "write_shared_memory", "delegate_scope"}
)


@dataclass(frozen=True)
class IntentManifest:
    case_id: str
    allowed_tool: str | None
    required_arguments: tuple[tuple[str, str], ...] = ()

    @classmethod
    def deny_effects(cls, case_id: str) -> "IntentManifest":
        return cls(case_id=case_id, allowed_tool=None)

    @classmethod
    def allow_effect(
        cls,
        case_id: str,
        tool: str,
        required_arguments: dict[str, str],
    ) -> "IntentManifest":
        if tool not in PROTECTED_EFFECTS:
            raise ValueError(f"not a protected effect: {tool}")
        return cls(
            case_id=case_id,
            allowed_tool=tool,
            required_arguments=tuple(sorted(required_arguments.items())),
        )


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    latency_ns: int


def authorize_effect(
    manifest: IntentManifest,
    tool: str,
    arguments: dict[str, Any],
) -> PolicyDecision:
    """Authorize a protected MCP call against explicit user intent."""

    started = perf_counter_ns()
    if tool not in PROTECTED_EFFECTS:
        return PolicyDecision(True, "not_protected", perf_counter_ns() - started)
    if manifest.allowed_tool is None:
        return PolicyDecision(False, "no_effect_authorized", perf_counter_ns() - started)
    if tool != manifest.allowed_tool:
        return PolicyDecision(False, "wrong_effect", perf_counter_ns() - started)
    for key, expected in manifest.required_arguments:
        if str(arguments.get(key, "")) != expected:
            return PolicyDecision(
                False,
                f"argument_mismatch:{key}",
                perf_counter_ns() - started,
            )
    return PolicyDecision(True, "intent_match", perf_counter_ns() - started)


class SingleUseIntentGate:
    """Consume an authorised effect once to prevent duplicate/replay commits."""

    def __init__(self, manifest: IntentManifest) -> None:
        self.manifest = manifest
        self.consumed = False

    def authorize(self, tool: str, arguments: dict[str, Any]) -> PolicyDecision:
        started = perf_counter_ns()
        decision = authorize_effect(self.manifest, tool, arguments)
        if not decision.allowed or tool not in PROTECTED_EFFECTS:
            return PolicyDecision(
                decision.allowed,
                decision.reason,
                perf_counter_ns() - started,
            )
        if self.consumed:
            return PolicyDecision(
                False,
                "intent_already_consumed",
                perf_counter_ns() - started,
            )
        self.consumed = True
        return PolicyDecision(True, "intent_match_consumed", perf_counter_ns() - started)
