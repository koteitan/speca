---
sidebar_position: 2
---

# Proof-Attempt Based Auditing

## From "Look for Bugs" to "Try to Prove"

Conventional LLM-based tools operate on vague instructions:

```
"Please check whether this code has any bugs"
```

The result is speculative and weakly grounded. **FP rate of 88%**.

SPECA demands a structured claim:

```
"Please prove whether this property holds:
 'authenticate() is always called before sensitive_data()'"
```

## Proof Gap = Finding Candidate

A proof-attempt arrives at one of three conclusions:

1. **Proof Success**: the property holds → NO_FINDING
2. **Proof Gap**: there is a part that cannot be proven → FINDING candidate
3. **Proof Failure**: the property does not hold → CONFIRMED_VULNERABILITY

A **proof gap** is the core of detection. The concrete gap (code location, condition) is identified:

```
Claim: "authenticate() is called before sensitive_data()"

Gap at line 85 in error_handler():
  if (!cache_hit) {
    sensitive_data();  // <-- authenticate() not called
  }
```

## Suppressing Hallucination

A structured claim suppresses speculation through:

- **Commitment**: the model clearly judges "this code satisfies / does not satisfy property X"
- **Gap articulation**: if it is an FP, it must explain a concrete gap
- **3-gate filter**: among proof gaps, those outside the trust boundary / scope are judged as FPs

## Implementation in Phase 03

```
Map:  map the property onto the code
  ↓
Prove: ask "does the property hold?"
  ↓
Stress-Test: try edge cases
```

See [Pipeline - Phase 03](../pipeline/audit-map.md) for details.
