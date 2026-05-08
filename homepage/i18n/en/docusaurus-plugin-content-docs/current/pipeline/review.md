---
sidebar_position: 7
---

# Phase 04: Review (3-Gate FP Filter)

A structured 3-gate review that reduces false positives. Recall-safe by design.

## Input

The output of Phase 03 (`outputs/03_PARTIAL_*.json`).

## The three gates (executed in order)

### Gate 1: Dead Code

- Determines whether the code location is unreachable.
- Detects unreachable code, stubs, and placeholders.
- Verdict: `DISPUTED_FP` (early exit).

### Gate 2: Trust Boundary

- Checks whether the proof gap crosses a trust boundary.
- Determines whether the input is attacker-controllable or comes from an internal call.
- Verdict: `DISPUTED_FP`, or proceed to the next gate.

### Gate 3: Scope Check

- Checks whether the issue is within the bug-bounty scope.
- Follows `BUG_BOUNTY_SCOPE.json`.
- Returns `DISPUTED_FP` if out of scope.

## Early exit

When any gate returns `DISPUTED_FP`, processing stops; subsequent gates are not executed.

## Output

`outputs/04_PARTIAL_*.json` — six verdicts:

```json
{
  "property_id": "PROP-001",
  "finding_id": "FINDING-001",
  "verdict": "CONFIRMED_VULNERABILITY",
  "gate_results": [
    {"gate": "dead_code", "passed": true},
    {"gate": "trust_boundary", "passed": true},
    {"gate": "scope_check", "passed": true}
  ],
  "severity": "HIGH"
}
```

| Verdict | Meaning |
|---|---|
| `CONFIRMED_VULNERABILITY` | High-confidence vulnerability (passed all gates) |
| `CONFIRMED_POTENTIAL` | Potential issue (out of scope but significant) |
| `DISPUTED_FP` | False positive (rejected by a gate) |
| `DOWNGRADED` | Severity downgraded (informational level) |
| `NEEDS_MANUAL_REVIEW` | Difficult to judge (manual review required) |
| `PASS_THROUGH` | Other |

For details, see [3-Gate Review](../concepts/gate-review.md).
