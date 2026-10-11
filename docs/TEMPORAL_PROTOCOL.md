# A request across an enforcement update

The [temporal example](../examples/temporal_quickstart.py) demonstrates why
placement verification and request lifetime need to be connected. It uses only
an in-memory sandbox ledger and the standard library.

## Initial route

The graph has `s → a → b → c → t`, plus the shortcut `s → b`. Node `s` is an
influence source, `b` a queue, and `t` the protected local effect. Eligible
enforcement locations `a`, `c` and `t` have example costs 1, 2 and 20.

Epoch 0 selects `c`: selecting `a` alone would leave the shortcut unmediated.
Two requests with the same approved action pause at `b` before crossing `c`.

## Activate a new placement

Removing the shortcut allows epoch 1 to select the cheaper location `a`.
New requests use epoch 1. The queued requests are already beyond `a`, so using
only the new placement for them would move their check behind their execution.

EpochCut retains epoch 0 for those requests. They still have to cross `c`.
A child created through a declared delegation edge also retains its admitted
epoch, but has its own identity and cannot widen the approved action.

## Resume and record

The first queued request substitutes a different destination. The retained check
at `c` denies it. The second keeps the approved action and receives a matching
grant. The broker validates that grant and current authority before recording
the action once. A duplicate recording attempt is denied.

Finally, both request references are released. Epoch 0 can then retire. Retaining
an epoch never bypasses current revocation, cancellation or expiry checks.

```bash
python examples/temporal_quickstart.py
```

The operation label in the example is `send_email`, but no message is sent.
It represents a local test record. This walkthrough is not a benchmark or a
claim about external delivery. Read [Architecture](ARCHITECTURE.md) for the trust
boundary and [API reference](API_REFERENCE.md) for the callable interfaces.
