"""A queued action survives an enforcement update without widening authority.

No API key, network service or external effect is used. The operation name is a
sandbox test label; the broker records rows and never sends email.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from epochcut.temporal import Broker, moving_graph


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    approved = {"tool": "send_email", "arguments": {
        "to": "approved@example.test", "body": "Approved sandbox action"}}
    substituted = {"tool": "send_email", "arguments": {
        "to": "other@example.test", "body": "Substituted sandbox action"}}
    broker = Broker(*moving_graph())
    try:
        require(broker.configs[0].placements["effect"] == frozenset({"c"}),
                "Epoch 0 must place the check at c")
        good = broker.begin("approved-workflow", "s", approved)
        bad = broker.begin("substituted-workflow", "s", approved)
        for token in (good, bad):
            require(broker.advance(token, "b", "queue", approved)["allowed"],
                    "Request must reach the queue")
        print("1. Epoch 0: two requests queued before enforcement point c.")

        update = broker.admit(*moving_graph(shortcut=False))
        require(update["accepted"], "Epoch 1 must activate")
        require(broker.configs[1].placements["effect"] == frozenset({"a"}),
                "Epoch 1 must move the check to a")
        require(0 in broker.configs, "Pending work must retain epoch 0")
        print("2. Epoch 1: new requests use a; pending requests retain epoch 0.")

        denied = broker.advance(bad, "c", "queue", substituted)
        require(not denied["allowed"] and denied["reason"] == "exact_intent_mismatch",
                "The retained check must deny action substitution")
        broker.finish(bad, cancel=True)
        print("3. Substituted action: DENIED by retained enforcement point c.")

        for node, interface in (("c", "queue"), ("t", "effect")):
            routed = broker.advance(good, node, interface, approved)
            require(routed["allowed"] and routed["epoch"] == 0,
                    "Approved pending work must use epoch 0")
        require(broker.commit(good, approved)["committed"],
                "The approved action must be recorded")
        require(not broker.commit(good, approved)["committed"],
                "Duplicate recording must be denied")
        print("4. Approved action: RECORDED once in the sandbox ledger.")

        broker.finish(good)
        require(0 not in broker.configs, "Unreferenced epoch 0 must retire")
        require(len(broker.effects()) == 1, "Exactly one sandbox row must exist")
        print("5. Epoch 0: RETIRED after its last active request finishes.")
        print("PASS: retained checks, action binding, duplicate denial and cleanup.")
    finally:
        broker.close()


if __name__ == "__main__":
    main()
