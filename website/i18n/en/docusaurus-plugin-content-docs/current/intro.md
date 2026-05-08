---
sidebar_position: 1
---

# What is SPECA

SPECA (Specification-to-Property Agentic Auditing) is an automated security audit framework that derives security properties from specifications and verifies, via proof-based auditing, whether the implementation satisfies them.

## Why start from the specification

Security tools that focus on scanning codebases can detect known bug patterns and dataflow anomalies. However, in systems that are governed by a specification (protocol implementations, cryptographic libraries, consensus engines, and the like), the root cause of a vulnerability sometimes lies not in "how the code is written" but in "what the specification requires." Tools that look only at code have no way to express specification-level invariants and therefore miss such defects.

SPECA reasons in the opposite direction. It reads the specification, derives formal security properties, and then asks whether the implementation can prove them.

## Approach in brief

1. **Derive properties from the specification**: Decompose the specification into a program graph, then apply STRIDE (a threat-modeling methodology) and the CWE Top 25 to generate security properties.
2. **Proof-attempt-based audit**: For each property, attempt to prove that it holds in the implementation. Report any portion that cannot be proven (a proof gap) as a candidate finding.
3. **3-gate false-positive filter**: Trim false positives through three sequential gates — Dead Code, Trust Boundary, and Scope Check. The design is recall-safe (it does not drop true positives).

## Track record

- **Sherlock Ethereum Fusaka**: Detected all 15 in-scope vulnerabilities. Also discovered 4 novel bugs not present in any of the 366 submissions (confirmed by the developers' fix commits).
- **RepoAudit C/C++ benchmark**: Achieved 88.9% precision while uncovering 12 new bug candidates beyond the established ground truth.

## Supported languages

Any system governed by a specification is supported, regardless of language. SPECA has been validated on Go, Rust, Nim, TypeScript, C, Solidity, and others.

## Next steps

Proceed to [Installation](./getting-started/installation.md), or run your first audit via [Try it now](./guide/try-it.md).
