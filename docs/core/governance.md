# Governance

AAAX governance is implemented through three cooperating pieces: capabilities, action authorization, and lifecycle.

## Capability manager

The `CapabilityManager` issues short-lived AAAX-local tokens for mediated resources. Each token is bound to:

- the requesting `system_id`
- a `resource`
- an `access` level
- an expiration time

AAAX validates both the token and the requesting system identity before approving a gated operation.

## Action gate

The `ActionGate` consumes requests from `aaax.action-gate` and expects a payload shaped like this:

```python
{
    "action": "send_email",
    "executor": "ops.mailer",
    "target": "ops://mail/outbound",
    "payload": {"subject": "...", "body": "..."},
    "capability": "<token>",
    "risk_level": "medium",
}
```

The gate then:

1. validates the execute capability
2. evaluates the action through policy
3. returns `action_approved`, `action_denied`, or `action_escalated`

AAAX is strongest when side effects actually flow through AAAX-owned executors. Approval without mediation is only a policy signal, not a hard boundary.

## Lifecycle manager

Lifecycle messages target docked systems and support:

- `revoke`
- `pause`
- `resume`
- `drain`

These are cooperative controls. AAAX uses them to manage the constellation coherently, but the exact runtime effect still depends on the underlying system implementation.

## Kernel reply channel

Governance responses are returned through the kernel mailbox channel `aaax.kernel-replies`, using the request sender as the mailbox recipient and the request message ID as the correlation ID.

## Important boundary

!!! warning
    AAAX does not claim that a local in-process SSSN connection is the same thing as capability-mediated authority. Local wiring is topology authority. AAAX capabilities are for mediated resources and AAAX-owned execution paths.
