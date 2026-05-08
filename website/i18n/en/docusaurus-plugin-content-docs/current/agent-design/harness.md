---
sidebar_position: 2
---

# Harness

The async Python orchestrator under `scripts/orchestrator/` is the *harness* — the layer between the user invocation (`speca run --target 04`) and the per-batch Claude calls. It is responsible for everything that has to be true regardless of which phase is running: parallelism, retry semantics, cost enforcement, resume behavior, and structured logging.

## Module map

| Module | Responsibility |
|---|---|
| `config.py` | `PhaseConfig` Pydantic model — declares prompt path, IO globs, batch strategy, circuit breaker thresholds, cost limits, MCP servers, tool whitelist |
| `base.py` | `BaseOrchestrator` — loads inputs, validates with Pydantic, applies resume filter, batches, executes via asyncio.gather |
| `runner.py` | `ClaudeRunner` — spawns `claude` CLI per batch with `--prompt-path` and `--stream-json`; owns `CircuitBreaker` and retry-with-backoff |
| `watchdog.py` | `LogWatcher` (real-time stream-json tail) + `CostTracker` (USD budget; raises `BudgetExceeded`) |
| `resume.py` | `ResumeManager` — scans `*_PARTIAL_*.json` to derive the set of already-processed item IDs |
| `collector.py` | `ResultCollector` — saves partials immediately; lenient validation (warns but doesn't block) |
| `schemas.py` | Pydantic models for every inter-phase contract |

## End-to-end execution flow

```
speca run --target 04
        │
        ▼
┌───────────────────────┐
│  PhaseConfig          │  ← config.py picks the per-phase definition
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│  ResumeManager        │  ← scans outputs/<phase>_PARTIAL_*.json
│  → already-done IDs   │     and skips items that already produced
└───────────┬───────────┘     a partial result
            ▼
┌───────────────────────┐
│  Batch builder        │  ← splits remaining work into N queue files
└───────────┬───────────┘     (one per worker)
            ▼
┌─────────────────────── parallel × workers ──────────────────────────┐
│  ClaudeRunner          ClaudeRunner          ClaudeRunner           │
│   • spawn `claude`      • spawn `claude`      • spawn `claude`      │
│   • LogWatcher          • LogWatcher          • LogWatcher          │
│   • token accounting    • token accounting    • token accounting    │
│   • retry on transient  • retry on transient  • retry on transient  │
└─────────────────────────────────┬────────────────────────────────────┘
                                  ▼
┌───────────────────────┐    ┌───────────────────────┐
│  ResultCollector      │    │  CostTracker          │
│  → PARTIAL_*.json     │    │  → BudgetExceeded     │
└───────────┬───────────┘    └───────────┬───────────┘
            ▼                            ▼
            └────────► next phase   ─►  exit code 64 (hard stop)
```

## Circuit breaker

A single shared instance per phase. Trips when any of the following thresholds is crossed:

| Counter | Default trip threshold | Why |
|---|---|---|
| `consecutive_failures` | 5 | Systemic problem (bad prompt, model outage). Continuing only burns budget |
| `total_retries` | 20 | Even with intermittent transients, this much retry indicates a structural issue |
| `consecutive_empty_results` | 3 | Empty output is usually a `MaxTurnsExhausted` symptom or a prompt regression |

When the breaker trips it raises `CircuitBreakerTripped`, the orchestrator cancels in-flight tasks and exits with code **65**. The state collected so far is preserved as partials.

## Retry semantics

Retry is bounded and **does not** apply to all failures.

| Failure | Retry? | Note |
|---|---|---|
| Transient API error (rate limit, 5xx) | Yes — exponential backoff, max 3 attempts | Most common case |
| `MaxTurnsExhausted` | **No** | Deterministic; retrying produces the same output |
| Schema-validation failure on output | No | The collector logs and writes the partial anyway (lenient) |
| `BudgetExceeded` | No | Exit immediately |
| `CircuitBreakerTripped` | No | All workers cancel |

The `MaxTurnsExhausted` distinction is important: it would be wasteful to retry a deterministic failure, and silently doing so would inflate the cost ceiling.

## Cost tracking and budgets

`CostTracker` extracts token usage from each batch's stream-json output and accumulates USD spend per phase. The price model is keyed by the model the phase uses. When a `--budget <usd>` flag is set, the tracker raises `BudgetExceeded` the moment the sum crosses the cap; the runner converts that to **exit code 64**.

Two operational implications:

- **Cost is bounded per phase, not per CLI run.** A six-phase run with `--budget 50` can consume $50 in any one phase; for tighter control, run individual phases.
- **The dashboard shows running cost in real time.** This is what the LogWatcher is for: it tails the stream-json and emits cost events to the TUI.

## Resume

Resume is the cheapest token-saving feature in the harness. Before a phase runs:

1. `ResumeManager` reads every `outputs/<phase>_PARTIAL_*.json` file.
2. It builds the set of `item_id`s that already produced a result.
3. The batch builder filters those IDs out of the queues.

This makes `Ctrl-C` safe (the next run resumes), and re-runs of a partially-failed phase free. `--force` clears the resume filter and re-runs everything.

## Partial files: a design choice, not an implementation detail

Every `ResultCollector` writes a partial after each batch. This means:

- **A crashed run never costs more than the batch in flight.**
- **Validation is lenient by design.** A schema mismatch on a single result is a warning, not a hard stop — the partial is still written so the next phase can consume it.
- **Resume is just a directory scan.** No state DB, no run UUIDs, no orphan-cleanup choreography.

The trade-off: the output directory accumulates files over time. `--cleanup-dry-run` reports what could be removed; the choice to actually delete is left to the user, because partials are how reproducibility is preserved.

## Worker / batch sizing

`PhaseConfig.batch_strategy` declares how items are grouped per Claude invocation. For most phases, batch size is 1 — the prompt is sized to one property at a time, and parallelism comes from running many workers concurrently. The `--workers` flag sets the worker count and `--max-concurrent` caps the simultaneous Claude processes.

Empirically (RQ2 reproductions), `--workers 4 --max-concurrent 8` saturates a single API key without hitting rate limits. Larger fleets need shared rate-limit accounting that isn't yet built in.

## Where to read the code

If you want to extend the harness, start in this order: `config.py` (declarative shape), `base.py` (orchestration logic), `runner.py` (process management), `watchdog.py` (cost + log streaming). The dependency graph is intentionally shallow — each module is under 600 LOC.
