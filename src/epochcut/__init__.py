"""Public API for the EpochCut research prototype."""

from .engine import AdmissionDecision, ClosureCertificate, EpochCutEngine, verify_certificate
from .graph import Edge, InfluenceGraph, Mutation, Node, RiskPolicy
from .mcp_policy import (
    PROTECTED_EFFECTS,
    IntentManifest,
    PolicyDecision,
    SingleUseIntentGate,
    authorize_effect,
)

__version__ = "0.1.0"

__all__ = [
    "AdmissionDecision",
    "ClosureCertificate",
    "Edge",
    "EpochCutEngine",
    "InfluenceGraph",
    "IntentManifest",
    "Mutation",
    "Node",
    "PROTECTED_EFFECTS",
    "PolicyDecision",
    "RiskPolicy",
    "SingleUseIntentGate",
    "authorize_effect",
    "verify_certificate",
]
