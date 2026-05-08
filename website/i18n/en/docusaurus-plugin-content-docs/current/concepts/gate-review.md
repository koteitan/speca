---
sidebar_position: 3
---

# 3-Gate Review (Recall-Safe FP Filter)

FINDING candidates produced by the proof-based audit in Phase 03 are validated through three mechanical gates.

## Design Principle: Recall-Safe

- **Recall**: preserve the detection rate of H/M/L vulnerabilities (target >90%)
- **Precision**: systematically reduce false positives

The empirical claim — recall stays at 100% while precision rises from 56.9% to 66.7% — is shown directly on RQ1 data:

![Phase 03 vs Phase 04 — recall, precision, F1](/img/charts/rq1_phase_comparison.png)

This tension is resolved by designing the gates to be "narrow" (with strict rejection conditions):

- A gate only returns DISPUTED_FP (other reductions are performed in earlier stages)
- FP reduction outside the three gates is not allowed (preserving recall while securing precision)

## Gate 1: Dead Code

**Question**: Is the code location of the proof gap actually reachable?

- Reduction targets:
  - Code immediately after `unreachable` / `panic!` / `return`
  - Stubs / placeholders / TODO comments
  - Test code / non-operational branches

- Verdict: **DISPUTED_FP** (early exit)

## Gate 2: Trust Boundary

**Question**: Does the proof gap cross a trust boundary?

Whether the input is attacker-controllable or internal logic:

- ✓ in_scope (untrusted input): continue to Gate 3
- ✗ out_of_scope (internally generated): **DISPUTED_FP** (early exit)

## Gate 3: Scope Check

**Question**: Is it within the target scope per BUG_BOUNTY_SCOPE.json?

```json
{
  "in_scope": ["src/auth.rs", "src/crypto/*"],
  "out_of_scope": ["tests/", "docs/"],
  "severity_classification": {
    "HIGH": [...],
    "MEDIUM": [...]
  }
}
```

- Verdict: **DISPUTED_FP** or **CONFIRMED_VULNERABILITY**

## Early Exit Behavior

When a gate returns DISPUTED_FP, subsequent gates are not executed:

```
Gate 1 → DISPUTED_FP ⇒ STOP (no Gate 2, 3)
Gate 1 → PASS ⇒ Gate 2
Gate 2 → DISPUTED_FP ⇒ STOP (no Gate 3)
Gate 2 → PASS ⇒ Gate 3
Gate 3 → DISPUTED_FP or CONFIRMED ⇒ STOP
```

## The Six Final Verdicts

| Verdict | Condition |
|---|---|
| `CONFIRMED_VULNERABILITY` | Passes all gates, high confidence |
| `CONFIRMED_POTENTIAL` | Latent but important |
| `DISPUTED_FP` | Rejected at Gate 1/2/3 |
| `DOWNGRADED` | Demoted to informational level |
| `NEEDS_MANUAL_REVIEW` | Difficult to judge |
| `PASS_THROUGH` | Other |

For implementation details, see [Pipeline - Phase 04](../pipeline/review.md). For the per-gate verified-FP rate on the same RQ1 data, see [Results / 3-gate filter effectiveness](../results-overview.md#per-gate-verified-fp-rate).
