---
sidebar_position: 1
---

# The Idea Behind Specification-Driven Auditing

## Limits of Code-Driven Tools

Conventional security tools detect known bug patterns:

- CWE-89: SQL injection (template: `query = "SELECT * FROM users WHERE id=" + user_input`)
- CWE-22: Path traversal (template: `open(userpath)` without sanitize)
- Memory corruption, race conditions, etc.

However, **in systems governed by a specification, vulnerabilities arise as violations of spec-level invariants**. They cannot be expressed by local pattern matching on code:

- Cryptographic protocols: mathematical invariants such as "message authentication holds" or "independence of randomness"
- State machines: requirements such as "in this state, transitioning to state X is forbidden"
- Consensus: "verification of this block must always preserve a safety invariant"

## The Specification-Driven Approach

SPECA analyzes in the reverse direction:

1. **Derive typed properties from the specification**
   - Invariant: a condition that must always hold
   - Precondition: a requirement before function execution
   - Postcondition: a guarantee after execution
   - Assumption: a dependency on an external system

2. **Ask the implementation to "try to prove this property"**
   - Proof gap = vulnerability candidate

3. **Recall-safe FP filtering**
   - 3-gate review: Dead Code / Trust Boundary / Scope
   - Systematically reduces FPs while preserving the detection rate

## Advantages

| Aspect | Benefit |
|---|---|
| **Detection** | Discovers vulnerabilities that are only definable at the specification level |
| **Traceability** | Each detection is traceable back to property → subgraph → spec section |
| **Comparative analysis** | N implementations can be evaluated under the same property vocabulary |
| **FP diagnosis** | FPs decompose into three grounded causes (trust boundary / code misreading / spec misunderstanding) |

See [Proof-Attempt Based Auditing](./proof-attempt.md) for details.
