---
sidebar_position: 6
---

# Phase 03: Audit Map (Proof-Based)

A formal, proof-attempt-based audit. For each property, it executes Map → Prove → Stress-Test in sequence.

## Input

- The output of Phase 02c (`outputs/02c_PARTIAL_*.json`).
- The target codebase (at the commit specified in `TARGET_INFO.json`).

## Processing

The three audit phases are executed in order:

### 1. Map

- Scans the code according to each property's `code_scope`.
- Identifies the relevant functions and variables.

### 2. Prove

- Asks "Does this property hold?"
- Attempts a proof.
- A **proof gap** (a hole in the proof) becomes a candidate finding.
- Hallucination suppression: requires concrete proof claims.

### 3. Stress-Test

- Searches for counterexamples to the proof.
- Verifies that the property holds in edge cases.
- Checks boundary conditions.

## Output

`outputs/03_PARTIAL_*.json`

```json
{
  "property_id": "PROP-001",
  "verdict": "FINDING",
  "proof_attempt": {
    "claim": "verify_auth() is always called before resource access",
    "evidence": "Code path exists where resource access occurs at line 85 without prior verify_auth() call",
    "confidence": "HIGH",
    "proof_gap": "Missing auth check in error handler at line 85"
  }
}
```

- `verdict`: FINDING / NO_FINDING / UNCERTAIN.
- `proof_gap`: the concrete gap in the proof (the target of filtering in Phase 04).

For details, see [Proof-attempt-based auditing](../concepts/proof-attempt.md).
