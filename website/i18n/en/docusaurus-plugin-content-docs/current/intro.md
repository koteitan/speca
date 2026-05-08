---
sidebar_position: 1
---

# What is SPECA

SPECA (Specification-to-Property Agentic Auditing) is an automated security audit framework that derives security properties from specifications and verifies — through proof-based auditing — whether the implementation satisfies them.

![SPECA pipeline at a glance](/img/diagrams/pipeline.png)

The pipeline splits into two halves: **Knowledge Structuring** (read the spec, extract a graph, generate typed properties) and **Systematic Auditing** (resolve property → code, attempt a proof, mechanically filter false positives).

## Why start from the specification

Security tools that focus on scanning codebases can detect known bug patterns and dataflow anomalies. But in systems governed by a specification — protocol implementations, cryptographic libraries, consensus engines — the root cause of a vulnerability sometimes lies not in "how the code is written" but in "what the specification requires." Tools that look only at code have no way to express specification-level invariants and therefore miss such defects.

SPECA reasons in the opposite direction. It reads the specification, derives formal security properties, and then asks whether the implementation can prove them.

## Approach in brief

1. **Derive properties from the specification.** Decompose the specification into a program graph, then apply STRIDE (a threat-modeling methodology) and the CWE Top 25 to generate typed security properties.
2. **Proof-attempt-based audit.** For each property, attempt to prove that it holds in the implementation. Report any portion that cannot be proven (a *proof gap*) as a candidate finding.
3. **3-gate false-positive filter.** Trim false positives through three sequential gates — Dead Code, Trust Boundary, Scope Check. The design is *recall-safe*: it does not drop true positives.

## Track record

- **Sherlock Ethereum Fusaka.** Detected all 15 in-scope H/M/L vulnerabilities. Also discovered 4 novel bugs not present in any of the 366 contest submissions (confirmed by the developers' fix commits).
- **RepoAudit C/C++ benchmark (ICML 2025).** Achieved 88.9% precision while uncovering 12 author-validated bug candidates beyond the published ground truth.

See [Results overview](./results-overview.md) for the headline charts.

## Supported languages

Any system governed by a specification is supported, regardless of language. SPECA has been validated on Go, Rust, Nim, TypeScript, C, Solidity, and others.

## Where to go next

Pick the entry point that matches what you want to do.

| If you want to… | Start here |
|---|---|
| **Run an audit on your own repo** | [Try it now](./guide/try-it.md) → [CLI reference](./getting-started/cli-reference.md) |
| **Understand how SPECA works** | [How it works](./guide/how-it-works.md) → [Pipeline overview](./pipeline/overview.md) |
| **Study the agent / harness design** | [Agent design overview](./agent-design/overview.md) |
| **Reproduce paper numbers** | [Operations](./operations/overview.md) |
