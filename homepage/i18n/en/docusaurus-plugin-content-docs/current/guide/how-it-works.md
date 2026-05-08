---
sidebar_position: 2
---

# How it works

SPECA executes six stages (Phases) in sequence. Each stage is described below in plain terms, followed by its internal technical name.

## 1. Collect specifications (Phase 01a)

Automatically discovers project specifications and documentation (GitHub Issues, scope definitions, and so on) from the internet.

## 2. Parse the specifications (Phase 01b)

Converts the collected specifications into state-transition diagrams. Flows such as "the user calls login" and "process_data is then executed" are reorganized into a structure that is easy for a computer to handle. The diagrams use the Mermaid format, and each state is also annotated with invariants.

## 3. Derive security properties (Phase 01e)

Automatically generates security-critical conditions — such as "is confidential data accessed before authentication?" or "is an authorization check missing?" — from the specifications. The judgments are guided by STRIDE (a threat-modeling methodology) and the CWE Top 25 (a list of common vulnerabilities). The conditions produced in this stage are called "security properties."

## 4. Decide where to look in the code (Phase 02c)

In preparation for verifying the security properties, identify in advance the locations in the implementation code that should be examined. Mappings such as "authentication is handled by the authenticate function in auth.py" or "data access is handled by the fetch function in database.py" are produced. This reduces token consumption in the next audit phase by 40-60%.

## 5. Inspect the code itself (Phase 03)

Reads the code and attempts to prove logically whether each security property holds. It investigates "is access really only possible after authentication?" in detail, and records any portion that cannot be proven (a proof gap) as a candidate finding.

## 6. Filter out false positives (Phase 04)

The candidates found in Phase 03 may include false positives (items that are not actually problems). Each candidate is passed through three gates in order — Dead Code, Trust Boundary, and Scope Check — leaving only genuine vulnerabilities. Which gate filtered a given candidate is also recorded, so the reasoning behind any false-positive determination can be traced.

## For readers who want more detail

- Pipeline details: [Pipeline documentation](../pipeline/overview.md)
- About proof-based auditing: [Proof-attempt-based auditing](../concepts/proof-attempt.md)
- Want to try it right away: [Try it now](try-it.md)
