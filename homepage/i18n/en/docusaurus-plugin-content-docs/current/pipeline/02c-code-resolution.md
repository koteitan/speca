---
sidebar_position: 5
---

# Phase 02c: Code Resolution (Tree-sitter)

Pre-resolves property definitions to concrete locations in the source code, using the Tree-sitter MCP.

## Prerequisites

- `outputs/TARGET_INFO.json` is required, containing the target repository and commit hash.
- `outputs/BUG_BOUNTY_SCOPE.json` (inherited from Phase 01e).

## Input

- The output of Phase 01e (`outputs/01e_PARTIAL_*.json`).
- `outputs/01b_SUBGRAPH_INDEX.json`, built from the Phase 01b output.
- The target codebase.

## Processing

1. **Build the subgraph index**: Indexes spec function names and state transitions from 01b partials.
2. **Tree-sitter symbol analysis**: Retrieves functions and structs via `mcp__tree_sitter__get_symbols`.
3. **Code location resolution**: Maps each property's entry point to a file and line range.
4. **Severity gate**: Drops items at the Informational level.

## Output

`outputs/02c_PARTIAL_*.json`

```json
{
  "property_id": "PROP-001",
  "type": "Invariant",
  "description": "Authentication state must be verified before accessing protected resources",
  "code_scope": {
    "file": "src/auth.rs",
    "line_range": [42, 68],
    "symbol": "verify_auth",
    "language": "rust"
  },
  "severity": "HIGH"
}
```

- `code_scope`: the concrete code location resolved by Tree-sitter.
- `severity`: the severity classification from `BUG_BOUNTY_SCOPE.json`.

This pre-resolution reduces token consumption in Phase 03 by 40-60%.
