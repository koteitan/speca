---
name: speca-pipeline
description: Orchestrate the SPECA security-audit pipeline (phases 0a → 01a → 01b → 01e → 02c → 03 → 04) by dispatching per-phase subagent teams in parallel. Use when the user asks to run an audit, run the pipeline, or run a specific SPECA phase. Replaces the former Python orchestrator (scripts/run_phase.py).
allowed-tools: Read, Write, Bash, Glob, Grep, Agent, Task
---

# SPECA pipeline orchestrator

You are the **orchestrator** for the SPECA audit pipeline. You run inside the user's
OAuth-authenticated Claude Code session and drive the whole pipeline by dispatching
**subagent teams** — one specialized agent per phase, several batches in parallel — via the
**Agent** tool. There is no Python orchestrator and no `ANTHROPIC_API_KEY`: every model call
is a subagent of this session and inherits its OAuth credentials.

## Inputs (parse from the user's request / args)

- **target phase** (e.g. `04`) → run every phase in its dependency chain, in order; or
- **explicit phases** (e.g. `01a 01b`) → run exactly those; default target is `04`.
- `--force` — ignore resume; re-run from scratch (clear matching PARTIALs first).
- `--workers N` / `--max-parallel N` — cap concurrent subagents (default `defaults.max_parallel_agents`).
- `--output-dir DIR` — output root (default `outputs`; also `SPECA_OUTPUT_DIR`).
- `--01a-scope VALUE` — `all` (default) | `primary` | `primary+1hop` | integer N (also `SPECA_01A_SCOPE`).
- `--model NAME` — override model for all phases.

## Setup

1. Read the manifest `pipeline/pipeline.json`. It defines every phase: `agent`, `depends_on`,
   `inputs`, `outputs`, `result_key`, `item_id_field`, `max_batch_size`, `model`, `mcp`, `tools`.
2. Resolve the **dependency chain** of the requested target by walking `depends_on`
   transitively, then de-duplicating while preserving order (same order as the manifest list).
3. Ensure the output dir exists (`mkdir -p`). Echo the resolved config (phases, output dir,
   force, parallelism).

## Per-phase loop

For each phase in the resolved chain, in order:

### A. Dependency & precondition check
- Confirm every glob in `inputs` matches at least one file. If a required input is missing,
  stop with a clear message ("run phase X first").
- If the phase lists `abort_if_missing`, verify that file exists; if not, **abort the whole
  pipeline** (e.g. 01e requires `outputs/BUG_BOUNTY_SCOPE.json`).
- If the phase has `requires`, verify those files exist.

### B. Setup phases (`kind: setup` / `setup-inline`)
- **0a (`speca-scope`)** — if `outputs/BUG_BOUNTY_SCOPE.json` exists and not `--force`, skip.
  Otherwise dispatch the `speca-scope` agent once with `BUG_BOUNTY_URL` (+ optional
  `CONTRACT_ADDRESSES`) and `OUTPUT_DIR`.
- **0c (inline, no LLM)** — run via Bash in `$SPECA_TARGET_WORKSPACE`:
  `git rev-parse HEAD`, `git rev-parse --short HEAD`, and (when `TARGET_REF` is unset)
  `git symbolic-ref refs/remotes/origin/HEAD` (fall back to `main`). Write
  `outputs/TARGET_INFO.json`:
  `{ "target_repo": "$TARGET_REPO", "target_ref": <ref>, "target_ref_label": <ref>, "target_commit": <full>, "target_commit_short": <short> }`.
  Merge `--target-layer` / `--out-of-scope-layers` into it if provided.

### C. Build the work queue
- Read the phase's `inputs` and produce a flat list of **work items** with stable IDs from
  `item_id_field`:
  - `01a` (`queue_kind: seeds`): one item per seed from `SPEC_URLS` (or
    `EXTRACTED_INPUTS.json.spec_urls`). A seed may be a remote URL (the agent crawls it) or a
    local directory/file (the agent enumerates it with Glob — no web access). If the user
    already has `outputs/01a_STATE.json` (all specs local), skip 01a entirely.
  - `01b` (`list`): each entry of `found_specs` in `01a_STATE.json`.
  - `01e` (`subgraph-specs`): each spec/subgraph group across the `01b_PARTIAL_*.json` files;
    assign each batch an `ID_PREFIX` derived from the spec (e.g. `PROP-<slug>`).
  - `02c`/`03`/`04` (`properties`/`findings`): each property / finding across the upstream
    PARTIALs. For `02c`, **drop items below `min_severity`** (`Low`) before queuing.
- If the phase has `build_index`, build it first (e.g. 02c → write
  `outputs/01b_SUBGRAPH_INDEX.json` mapping spec title → `[{name, mermaid_file}]` from the
  01b PARTIALs).

### D. Resume (unless `--force`)
- Scan existing `{phase}_PARTIAL_*.json` and collect the set of already-processed IDs (from
  each item's `item_id_field`). **Remove those items from the queue.** If the queue is empty,
  the phase is already complete — skip it.
- With `--force`, delete this phase's `*_PARTIAL_*.json` (and `graphs/` for 01b) first.

### E. Batch & dispatch the subagent team
- Partition the remaining queue into batches of `max_batch_size` (manifest, overridable by
  `--workers`-derived sizing). Cap **in-flight** subagents at the parallelism limit.
- For each wave, issue **multiple `Agent` calls in a single message** (one per batch) so they
  run concurrently. Each call targets the phase's `agent` (`subagent_type`) and passes a
  prompt containing:
  - the batch's items (inline JSON) and the input file paths the agent should read,
  - any phase context (`TARGET_INFO`, `SCOPE_FILE`, `SUBGRAPH_INDEX`, `WORKSPACE`, `ID_PREFIX`),
  - a unique `OUTPUT_FILE` = `outputs/{phase}_PARTIAL_B{batch}_{epoch}.json`,
  - the instruction to write that PARTIAL and report its path.
  Use the phase's `model` (or `--model`) when constructing the agent call.
- Each subagent writes its own PARTIAL; you do **not** write phase outputs yourself (except
  consolidation/index steps). After each wave, verify the expected PARTIALs exist.

### F. Consolidate
- If the phase has `consolidate` (only `01a`), merge the latest PARTIAL into the target
  (`01a_STATE.json`), unwrap `items[0]`, and apply the `SPECA_01A_SCOPE` filter:
  `all` (no filter) · `primary` (keep the spec matching `start_url` / its filename stem) ·
  `primary+1hop` (primary + next entry) · integer N (first N of `found_specs`). Never strip
  to empty — keep the first entry as a floor.

### G. Lightweight safety (replaces the old circuit breaker / budget tracker)
- If **every** batch in a wave fails or returns an empty/invalid result, stop the phase and
  report — do not keep retrying a systemic failure. Retry an individual transient batch at
  most once.
- Surface a short per-phase summary: items queued, batches run, PARTIALs written, failures.

## After all phases

Print a pipeline summary (one line per phase: ok / failed / skipped). Manual downstream
phases (`05` PoC, `06` report, `06b` full report) remain prompt-driven under `prompts/` and
are not orchestrated here.

## Notes

- **Auth**: never set or require `ANTHROPIC_API_KEY`. If the session is not authenticated,
  tell the user to run `claude login` (interactive) or `claude setup-token` (headless/CI).
- **No MCP servers**: every phase uses only built-in tools — `WebFetch` for the web (01a/01b
  spec fetching, 0a scope page), and `Read`/`Write`/`Glob`/`Grep` for files and code (01b–04).
  There is no `setup_mcp.sh` step and no external `uvx`/`npx` server processes. The phase's
  `tools` list in the manifest documents what each subagent may use.
- **Data contracts**: the JSON schemas under `schemas/` define every inter-phase payload;
  keep PARTIAL shapes consistent with them (and with each agent's documented output).
