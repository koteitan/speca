---
sidebar_position: 4
---

# Configuration files

`speca init` produces two JSON files under `outputs/`. They are the only inputs the pipeline needs from you. This page is the canonical schema reference.

## `outputs/TARGET_INFO.json`

Identifies the codebase under audit. Read by Phase 02c (to clone the right commit) and Phase 03 (to resolve relative paths).

```json
{
  "project_name": "lighthouse-audit-2026-05",
  "target_repo": "https://github.com/sigp/lighthouse",
  "target_commit": "v5.1.3",
  "target_language": "Rust",
  "target_layer": "consensus",
  "description": "Lighthouse Ethereum consensus client, v5.1.3"
}
```

| Field | Required | Notes |
|---|---|---|
| `project_name` | yes | Used in output paths and report titles |
| `target_repo` | yes | Public Git URL. SSH URLs are accepted if your SSH agent can reach them |
| `target_commit` | yes | Commit hash, branch, or tag. Pinning to a tag/hash is strongly recommended for reproducibility |
| `target_language` | yes | Free-form label; `tree_sitter` MCP picks the right parser based on file extensions, not this field |
| `target_layer` | no | Hint used by Phase 01e to bias which CWE templates apply |
| `description` | no | Free-form note for the report |

The repository is cloned under `target_workspace/` at run time; you do not commit it.

## `outputs/BUG_BOUNTY_SCOPE.json`

Defines what counts as in-scope and how severity is assigned. **Required by Phase 01e** — the orchestrator aborts with `sys.exit(1)` if it is missing.

```json
{
  "program_name": "ethereum-fusaka",
  "scope_version": "1.0",

  "in_scope": [
    "src/consensus/",
    "src/crypto/kzg.rs",
    "src/state_machine.rs"
  ],

  "out_of_scope": [
    "tests/",
    "docs/",
    "vendor/",
    "build/"
  ],

  "severity_classification": {
    "CRITICAL": {
      "description": "Protocol halt, cryptographic break",
      "cwe": ["CWE-327", "CWE-338"],
      "examples": ["Invalid signature verification", "Entropy exhaustion"]
    },
    "HIGH": {
      "description": "State divergence, consensus failure",
      "cwe": ["CWE-862", "CWE-863"],
      "examples": ["Unauthorized state transition", "Access control bypass"]
    },
    "MEDIUM": {
      "description": "Information disclosure, partial bypass",
      "cwe": ["CWE-200", "CWE-203"],
      "examples": ["Timing leak", "Nonce reuse"]
    },
    "LOW": {
      "description": "Quality, usability",
      "cwe": ["CWE-400"],
      "examples": ["Resource leak", "Performance degradation"]
    }
  },

  "scope_notes": "Only in-scope high-value code paths will be audited."
}
```

### Top-level fields

| Field | Required | Notes |
|---|---|---|
| `program_name` | yes | Identifier; appears in report headings |
| `scope_version` | no | Version label, e.g. when re-running with a tightened scope |
| `in_scope` | yes | Glob/path entries. Phase 04 Gate 3 keeps findings whose code path matches at least one |
| `out_of_scope` | no | Explicit excludes. Findings landing here are returned as `DISPUTED_FP` by Gate 3 |
| `severity_classification` | yes | Maps levels (`CRITICAL` / `HIGH` / `MEDIUM` / `LOW` / `Informational`) to CWE references and examples |
| `scope_notes` | no | Free-form notes propagated into reports |

### Why severity goes here, not in the code

Severity is a **program-specific** judgment (a "100% validators stuck" issue is `CRITICAL` in a consensus client and `HIGH` elsewhere). Phase 02c uses `severity_classification` to drop `Informational` properties before audit; Phase 03 reads it for context; Phase 04 calibrates the final severity. Centralizing it in this file is what makes the rest of the pipeline contest-agnostic — see [Operations / Reproducing RQ1](../operations/benchmark-rq1.md) for an example of swapping rubrics.

### Sharing a rubric across implementations

For multi-implementation audits (e.g. ten Ethereum clients implementing the same EIP), use a `common_rubric` block to reuse a single scope description:

```json
{
  "program_name": "kzg-batch-verify-v2",
  "common_rubric": {
    "in_scope": [
      "KZG parameter generation (setup)",
      "Commitment creation",
      "Batch verification (main algorithm)",
      "Polynomial operations"
    ],
    "out_of_scope": [
      "Serialization / deserialization",
      "Performance optimizations",
      "Logging / debugging"
    ]
  }
}
```

Each implementation then inherits the same property vocabulary, which is what enables [cross-implementation comparison](../concepts/spec-driven.md#advantages).

## Sanity checks

`speca doctor` verifies that both files load and their `severity_classification` parses. If you author them by hand, run:

```bash
speca doctor
```

before kicking off `speca run`. It reports the first parse error with line + column.
