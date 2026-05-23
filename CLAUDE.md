# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SPECA (Specification-to-Property Agentic Auditing) — an automated security audit pipeline that uses Claude Code to analyze codebases for vulnerabilities. The pipeline transforms specifications into formal program graphs, generates security properties, pre-resolves code locations, performs proof-based formal audits against target code, and filters false positives via a recall-safe 3-gate review pipeline (Dead Code, Trust Boundary, Scope Check).

The orchestration is **agent-teams native**: a Claude Code skill (`/speca-pipeline`) runs inside the user's OAuth-authenticated session and dispatches one specialized **subagent per phase** (in `.claude/agents/`), several batches in parallel, via the Agent tool. There is no Python orchestrator and no `ANTHROPIC_API_KEY` — every model call is a subagent of the host session and inherits its OAuth credentials. (See `changelog.md` for the before/after of this migration.)

## Commands

```bash
# Run tests (pre-flight check used in CI)
uv run python3 -m pytest tests/ -v --tb=short

# 1. Authenticate once (no API key)
claude login            # interactive
claude setup-token      # headless / CI

# 2. Run the pipeline from a Claude Code session (no MCP setup needed)
/speca-pipeline --target 04          # run the full dependency chain up to phase 04
/speca-pipeline 01a 01b              # run specific phases
/speca-pipeline --phase 03 --force   # force re-run, ignoring resume
```

## Architecture

### Orchestrator (`/speca-pipeline` skill + `pipeline/pipeline.json`)

The orchestrator is the `.claude/skills/speca-pipeline/SKILL.md` skill, driven by the declarative manifest `pipeline/pipeline.json` (the replacement for the former `config.py` `PHASE_CONFIGS`). For each phase in dependency order it:

1. **Reads the manifest** — every phase entry declares its `agent`, `depends_on`, `inputs`/`outputs`, `result_key`, `item_id_field`, `max_batch_size`, `model`, and `tools`.
2. **Checks preconditions** — required inputs exist; `abort_if_missing` files (e.g. 01e requires `outputs/BUG_BOUNTY_SCOPE.json`) are present.
3. **Builds the work queue** — flattens upstream PARTIALs into work items keyed by `item_id_field`; applies severity gates (02c drops `Informational`).
4. **Resumes** — scans existing `{phase}_PARTIAL_*.json`, skips already-processed IDs (unless `--force`).
5. **Dispatches the subagent team** — partitions the queue into batches and issues multiple `Agent` calls in a single message so batches run in parallel; each subagent reads its items and writes its own PARTIAL. Concurrency is capped by `--max-parallel`.
6. **Consolidates** — phase-specific merges (e.g. 01a PARTIAL → `01a_STATE.json` with the `SPECA_01A_SCOPE` filter; 02c builds `01b_SUBGRAPH_INDEX.json`).
7. **Lightweight safety** — stops a phase if every batch in a wave fails (replaces the old shared circuit breaker / cost tracker).

Phase 0 setup: **0a** scope extraction runs the `speca-scope` subagent; **0c** `TARGET_INFO.json` is generated inline by the orchestrator via `git` (no LLM call).

### Subagents (`.claude/agents/`)

One subagent per phase — the "team". Each `.md` has frontmatter (`name`, `description`, `tools`, `model`) and the migrated per-phase analysis logic + its `outputs/` I/O contract:
`speca-scope` (0a), `speca-spec-discovery` (01a), `speca-subgraph-extractor` (01b), `speca-property-generator` (01e), `speca-code-resolver` (02c), `speca-auditor` (03), `speca-reviewer` (04).

### Data contracts (`schemas/`)

The JSON schemas under `schemas/` define every inter-phase payload (01a→01b→01e→02c→03→04). They are the source of truth for PARTIAL shapes and are now hand-maintained (the former Pydantic generator was removed with the Python orchestrator).

### Pipeline Phases

Phase IDs: `01a` → `01b` → `01e` → `02c` → `03` → `04`

- **01a** Spec Discovery (`speca-spec-discovery`): discover specs from a seed — a remote URL (crawl via `WebFetch`) or a local dir/file (enumerate via `Glob`) → `outputs/01a_STATE.json`. If all specs are already local, 01a may be skipped by providing `01a_STATE.json` directly.
- **01b** Subgraph Extraction (`speca-subgraph-extractor`): specs → enriched Mermaid state diagrams (`.mmd` with YAML frontmatter + `note` invariant blocks) + `01b_PARTIAL_*.json`. Reads `local_path`/`file://` sources with `Read`, remote sources with `WebFetch`.
- **01e** Property Generation (`speca-property-generator`): trust model analysis (domain-agnostic STRIDE + CWE Top 25) + formal security properties from subgraphs (depends on 01b). **Requires** `outputs/BUG_BOUNTY_SCOPE.json` — the orchestrator aborts the pipeline if missing. Slim output: `covers` is a string (primary element ID), `reachability` has 4 fields only.
- **02c** Code Pre-resolution (`speca-code-resolver`): pre-resolve code locations (`code_scope`) for properties against the target repo using `Grep`/`Glob` (multi-tier fallback, metadata only — no excerpts). Requires `outputs/TARGET_INFO.json`. Also builds `outputs/01b_SUBGRAPH_INDEX.json` from 01b partials for spec-level context. Severity gate drops `Informational` properties. Model: Sonnet.
- **03** Audit Map (`speca-auditor`): proof-based 3-phase formal audit (Map → Prove → Stress-Test) against the target codebase. Tries to prove properties hold; gaps in proof are findings. Reads `outputs/TARGET_INFO.json` for the target repo/commit. One property per subagent invocation. Model: Sonnet. Tools: Read/Write/Grep/Glob only.
- **04** Review (`speca-reviewer`): 3-gate FP filter pipeline with early exit (Dead Code → Trust Boundary → Scope Check), then severity calibration. Only these 3 gates may produce DISPUTED_FP (recall-safe design). Verdicts: CONFIRMED_VULNERABILITY, CONFIRMED_POTENTIAL, DISPUTED_FP, DOWNGRADED, NEEDS_MANUAL_REVIEW, PASS_THROUGH. Model: Sonnet. Tools: Read/Write/Grep/Glob only.

Manual (not orchestrated): `05` PoC Generation, `06` Bug-Bounty Report, `06b` Full Audit Report.

### Skills & Agents System

- **Orchestrator skill** — `.claude/skills/speca-pipeline/SKILL.md` (`/speca-pipeline`) drives the whole pipeline.
- **Phase subagents** — `.claude/agents/speca-*.md`, one per phase (the "team").
- **Helper skills** — `.claude/skills/spec-discovery` and `subgraph-extractor` remain (`context: fork`) and are invoked by the 01a / 01b subagents when present.

All per-phase analysis logic now lives in the subagent definitions, not in separate worker prompts.

### Data Flow Convention

- **Output naming:** `outputs/{phase_id}_PARTIAL_B{batch}_{timestamp}.json` (each subagent writes its own).
- **Logs:** `outputs/logs/{phase_id}_B{batch}_{timestamp}.md`.
- Phases consume `PARTIAL_*.json` glob patterns from upstream phases. No queue files — the orchestrator passes each batch's items inline to its subagent.
- **01e slim schema:** `covers` = string (primary element ID, e.g. `"FN-001"`). `reachability` = 4 fields: `classification`, `entry_points`, `attacker_controlled`, `bug_bounty_scope`.

### Key Design Decisions

- **OAuth, not API key:** the pipeline runs as subagents of an OAuth-authenticated Claude Code session (`claude login` / `claude setup-token`). No `ANTHROPIC_API_KEY` anywhere.
- **No MCP servers:** web access is the built-in `WebFetch`; file/code access is `Read`/`Write`/`Glob`/`Grep`. The former `fetch`/`filesystem`/`tree_sitter` MCP servers (and `setup_mcp.sh`) are gone. Trade-off: 02c resolution is text-based (`Grep`/`Glob`) instead of AST-precise — it already had a multi-tier fallback, so it degrades gracefully.
- **Partial results are first-class:** every subagent writes its PARTIAL immediately. Resume scans these files to skip completed items.
- **Lightweight safety:** the orchestrator stops a phase if every batch in a wave fails (replaces the old shared circuit breaker + cost tracker). There is no hard budget enforcement layer — control cost by scoping phases and `--max-parallel`.
- **Phase 02c/03 target consistency:** `outputs/TARGET_INFO.json` is created once (phase 0c, inline `git`) and read by 02c/03/04, ensuring a single source of truth.
- **01b subgraph index for 02c:** the orchestrator builds `outputs/01b_SUBGRAPH_INDEX.json` from 01b partials; 02c uses it to map spec-level names → mermaid files for better code resolution.
- **Required bug_bounty_scope:** phase 01e requires `outputs/BUG_BOUNTY_SCOPE.json`; the orchestrator aborts the pipeline if it is missing. No hardcoded defaults.
- **Domain-agnostic STRIDE + CWE Top 25:** phase 01e uses a general STRIDE thinking framework augmented with CWE Top 25 patterns (CWE-22/78/89/94/200/502/639/770/862). No domain-specific hardcoding.

### Environment Variables

- `KEYWORDS`, `SPEC_URLS` — Phase 01a discovery inputs (a seed may be a URL or a local path).
- `SPECA_01A_SCOPE` — Filter Phase 01a state before 01b consumes it. Values: `all` (default), `primary`, `primary+1hop`, or a positive integer N. Equivalent to the `--01a-scope` flag (the flag wins).
- `BUG_BOUNTY_URL`, `CONTRACT_ADDRESSES` — Phase 0a scope extraction inputs.
- `SPECA_TARGET_WORKSPACE`, `TARGET_REPO`, `TARGET_REF` — Phase 0c `TARGET_INFO.json` inputs.
- `SPECA_OUTPUT_DIR` — Output root (default `outputs`).
