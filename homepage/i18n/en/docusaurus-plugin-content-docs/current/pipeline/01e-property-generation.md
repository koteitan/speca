---
sidebar_position: 4
---

# Phase 01e: Property Generation

Generates typed security properties from subgraphs, applying a STRIDE + CWE Top 25 threat model.

## Prerequisites

`outputs/BUG_BOUNTY_SCOPE.json` is required. If the file is missing, the orchestrator aborts with `sys.exit(1)`.

## Input

- The output of Phase 01b (`outputs/01b_PARTIAL_*.json`)
- `outputs/BUG_BOUNTY_SCOPE.json`

## Processing

1. **STRIDE threat model**: Spoofing / Tampering / Repudiation / Information Disclosure / Denial of Service / Elevation of Privilege.
2. **CWE Top 25**: CWE-22 (Path Traversal), CWE-78 (OS Command Injection), CWE-89 (SQL Injection), and others.
3. **Trust model analysis**: Identifies attacker-controllable input points from the subgraph.
4. **Property types**: Four classes
   - `Invariant` — a condition that must always hold
   - `Precondition` — a requirement before function execution
   - `Postcondition` — a guarantee after execution
   - `Assumption` — an assumption about an external system

## Output

`outputs/01e_PARTIAL_*.json`

```json
{
  "property_id": "PROP-001",
  "type": "Invariant",
  "description": "Authentication state must be verified before accessing protected resources",
  "covers": "FN-001",
  "classification": "STRIDE_ElevationOfPrivilege",
  "cwe_related": ["CWE-862"],
  "reachability": {
    "classification": "PUBLIC_API",
    "entry_points": ["authenticate()", "verify_token()"],
    "attacker_controlled": ["user_input", "token"],
    "bug_bounty_scope": "in_scope"
  }
}
```

- `covers`: the ID of the source subgraph element.
- `reachability`: reachability information derived from `BUG_BOUNTY_SCOPE.json`.

This file is consumed as input by Phase 02c (code resolution) and Phase 03 (audit).
