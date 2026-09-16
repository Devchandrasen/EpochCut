from __future__ import annotations

import unittest

from epochcut.mcp_policy import IntentManifest, SingleUseIntentGate, authorize_effect


class MCPPolicyTests(unittest.TestCase):
    def test_attack_case_denies_every_effect(self) -> None:
        manifest = IntentManifest.deny_effects("A-1")
        decision = authorize_effect(
            manifest,
            "send_email",
            {"recipient": "attacker@example.com", "body": "CANARY"},
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "no_effect_authorized")

    def test_benign_case_requires_exact_effect_arguments(self) -> None:
        manifest = IntentManifest.allow_effect(
            "B-1", "delegate_scope", {"principal": "review-bot", "scope": "read_only"}
        )
        self.assertTrue(
            authorize_effect(
                manifest,
                "delegate_scope",
                {"principal": "review-bot", "scope": "read_only"},
            ).allowed
        )
        self.assertFalse(
            authorize_effect(
                manifest,
                "delegate_scope",
                {"principal": "external-bot", "scope": "admin"},
            ).allowed
        )

    def test_non_effect_tool_is_not_blocked(self) -> None:
        manifest = IntentManifest.deny_effects("A-2")
        self.assertTrue(authorize_effect(manifest, "read_ticket", {"case_id": "A-2"}).allowed)

    def test_authorised_effect_is_consumed_once(self) -> None:
        gate = SingleUseIntentGate(
            IntentManifest.allow_effect(
                "B-2", "send_email", {"recipient": "audit@example.com"}
            )
        )
        arguments = {"recipient": "audit@example.com", "body": "Printer offline."}
        self.assertTrue(gate.authorize("send_email", arguments).allowed)
        replay = gate.authorize("send_email", arguments)
        self.assertFalse(replay.allowed)
        self.assertEqual(replay.reason, "intent_already_consumed")


if __name__ == "__main__":
    unittest.main()
