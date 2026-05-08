---
sidebar_position: 4
---

# BUG_BOUNTY_SCOPE.json

A metadata file used for scope determination, from Phase 01e (property generation) through Phase 04 (review).

## Required

`outputs/BUG_BOUNTY_SCOPE.json` is required when Phase 01e runs. If the file is absent, the orchestrator stops with `sys.exit(1)`.

## Schema

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
  
  "scope_notes": "Only in-scope high-value code paths will be audited. Test utilities and vendor code excluded per standard rubric."
}
```

## Where It Is Used

- **Phase 01e**: attaches `reachability.bug_bounty_scope` (in_scope/out_of_scope) to properties
- **Phase 02c**: maps to severity classification (drops Informational)
- **Phase 04 Gate 3**: checks whether the proof gap falls within in_scope

## How to Write a Custom Rubric

For cross-comparison across multiple implementations, use a shared rubric:

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

By sharing this file across multiple implementations, **comparison under the same property vocabulary** becomes possible.

See [Specification-Driven Auditing](./spec-driven.md) for details.
