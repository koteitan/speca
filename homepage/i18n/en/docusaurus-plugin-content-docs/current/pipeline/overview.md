---
sidebar_position: 1
---

# Pipeline Overview

SPECA consists of six ordered phases. The first two phases handle specification analysis (run only once), while the remaining four perform implementation auditing (run per target).

## Phase dependency chain

```
01a (Spec Discovery)
  ↓
01b (Subgraph Extraction)
  ↓
01e (Property Generation) ← BUG_BOUNTY_SCOPE.json required
  ↓
02c (Code Pre-resolution) ← TARGET_INFO.json required
  ↓
03 (Audit Map)
  ↓
04 (Review)
```

## Phases

| ID | Name | Input | Output |
|---|---|---|---|
| **01a** | [Spec Discovery](./01a-spec-discovery.md) | SPEC_URLS env | STATE.json |
| **01b** | [Subgraph Extraction](./01b-subgraph-extraction.md) | STATE.json | Mermaid + PARTIAL_*.json |
| **01e** | [Property Generation](./01e-property-generation.md) | Subgraph + STRIDE/CWE | PARTIAL_*.json |
| **02c** | [Code Resolution](./02c-code-resolution.md) | Properties + source | PARTIAL_*.json |
| **03** | [Audit Map](./audit-map.md) | Properties + code | PARTIAL_*.json |
| **04** | [Review](./review.md) | Findings | PARTIAL_*.json (6 verdicts) |

## Data flow

- **Partial files**: `outputs/<phase_id>_PARTIAL_W{worker}B{batch}_{timestamp}.json`
- **Queue files**: `outputs/<phase_id>_QUEUE_{worker}.json`
- **Logs**: `outputs/logs/{phase_id}_*.jsonl`

Each phase consumes upstream partial files via glob patterns, skips already-processed items (resume), and writes results immediately.

## Circuit breaker, budget, and resume

- **Circuit Breaker**: Shared across all workers. Automatically stops on consecutive errors or API anomalies.
- **Budget**: Hard-stops per phase via `BudgetExceeded`. Prevents token waste.
- **Resume**: Already-processed items are skipped automatically, saving tokens on interruption or re-execution.

For details, refer to each phase's documentation.
