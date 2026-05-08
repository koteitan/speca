---
sidebar_position: 1
---

# Agent design overview

This section documents how SPECA is built as an agent system: the prompts, the context flow between phases, and the harness that runs them. It is aimed at engineers who want to understand or adapt the design — not at end users.

The headline observation: **a system of LLM agents only behaves predictably when each agent's input contract is narrow and its output is verified at the boundary.** SPECA enforces this with three coordinated mechanisms, one per page in this section.

| Page | What it covers |
|---|---|
| [Harness](./harness.md) | The async Python orchestrator — circuit breaker, cost tracker, watchdog, resume manager, batch / queue / partial-file design |
| [Prompts and skills](./prompts-and-skills.md) | Skill-fork vs inline prompts, MCP-server wiring per phase, tool whitelists, model assignment |
| [Context engineering](./context-engineering.md) | The non-obvious choices: subgraph index, code pre-resolution, partial-file resume, recall-safe gate ordering |

If you only read one page, read [Context engineering](./context-engineering.md) — it captures the design decisions that aren't visible from reading the code alone.

## How the three layers fit together

```
┌──────────────────────────────────────────────────────────────────────┐
│  Harness  —  scripts/orchestrator/                                   │
│  ────────────────────────────────────────────────────────────────    │
│  • PhaseConfig defines IO contract per phase                         │
│  • BaseOrchestrator parallelises batches, manages resume             │
│  • ClaudeRunner spawns `claude` CLI per batch + circuit breaker      │
│  • CostTracker enforces budget via BudgetExceeded                    │
│  • LogWatcher tails stream-json logs in real time                    │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ invokes
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Prompts / Skills  —  prompts/ + .claude/skills/                     │
│  ────────────────────────────────────────────────────────────────    │
│  • 01a / 01b run as Claude Code skills (context: fork)               │
│  • 01e / 02c / 03 / 04 are inline prompts (no fork)                  │
│  • Each phase has its own model + tool whitelist + MCP servers       │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ produces
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Context flow  —  outputs/<phase>_PARTIAL_*.json                     │
│  ────────────────────────────────────────────────────────────────    │
│  • Pydantic schemas validate at every phase boundary                 │
│  • 01b_SUBGRAPH_INDEX.json — spec-level lookup for 02c               │
│  • 02c pre-resolution — saves 40-60% tokens in 03                    │
│  • Partial files are first-class — never overwritten                 │
└──────────────────────────────────────────────────────────────────────┘
```

## The four invariants the design enforces

1. **Validation at every phase boundary.** Every inter-phase write is a Pydantic model. A bad upstream output cannot silently corrupt a downstream phase.
2. **Partial progress is first-class.** Each batch writes a `PARTIAL_*.json` immediately. Resume scans these to skip processed items. A crashed run never costs more than the batch in flight.
3. **Cost is bounded per phase, not per call.** `CostTracker` accumulates per-phase USD and raises `BudgetExceeded` at the runner level. Exit codes propagate to CI.
4. **Failure modes are differentiated.** `MaxTurnsExhausted` (deterministic; no retry) is not the same as a transient API error (retry with exponential backoff) is not the same as a `CircuitBreakerTripped` (whole-phase abort).

These four invariants are what makes the pipeline reproducible enough to publish numbers against — without them, RQ1's "100% recall" would not be a stable claim.
