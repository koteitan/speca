---
sidebar_position: 3
---

# Prompts and skills

How each phase is wired up: which prompt drives it, whether it forks a Claude Code skill, which model runs it, which tools and MCP servers it can access.

## At a glance

| Phase | Prompt file | Skill fork? | Model | Tools | MCP |
|---|---|---|---|---|---|
| **01a** Spec Discovery | `prompts/01a_crawl.md` + `.claude/skills/spec-discovery/` | **Yes** | Opus | full | `fetch` |
| **01b** Subgraph Extraction | `prompts/01b_extract_worker.md` + `.claude/skills/subgraph-extractor/` | **Yes** | Opus | full | — |
| **01e** Property Generation | `prompts/01e_prop_worker.md` | No (inline) | Opus | full | — |
| **02c** Code Pre-resolution | `prompts/02c_codelocation_worker.md` | No (inline) | Sonnet 4.5 | Read / Write / Grep / Glob | `tree_sitter` |
| **03** Audit Map | `prompts/03_auditmap_worker_inline.md` | No (inline) | Sonnet 4.5 | Read / Write / Grep / Glob | — |
| **04** Review | `prompts/04_review_worker.md` | No (inline) | Sonnet 4.5 | Read / Write / Grep / Glob | — |

Manual phases (not driven by the orchestrator) live alongside: `05_poc.md`, `06_report.md`, `06b_audit_report.md`.

## Skill fork vs. inline prompt

Two phases (`01a`, `01b`) are implemented as Claude Code **skills** (`.claude/skills/<name>/SKILL.md`) with `context: fork`. The other four are **inline prompts** — the entire analysis instructions live in the worker prompt file the orchestrator hands to `claude --prompt-path`.

The split is deliberate:

- **Skills are right when the agent's job is exploratory and cross-cutting** — Phase 01a discovers spec links across many fetched documents; Phase 01b decomposes a spec section into a state machine. Forking a skill context isolates the long-running exploratory work from the orchestrator's main thread.
- **Inline prompts are right when the agent's job is bounded and per-item** — Phase 01e takes one subgraph and produces typed properties; Phase 03 takes one property and runs Map → Prove → Stress-Test. There is nothing to gain from forking a separate context, and inlining removes a layer of indirection (and one round trip of context-loading overhead).

We measured the inline conversion as roughly 15–25% faster per item with no quality regression. The model-benchmark numbers in [RQ2](../operations/benchmark-rq2a.md) were collected with the inline configuration.

## Tool whitelists per phase

The orchestrator passes a tool whitelist on every `claude` invocation. The whitelist matters for two reasons: it bounds what the agent can do (so a confused agent can't, say, call `git push`), and it limits the action space the model has to reason over.

**Phases 03 and 04** use `Read / Write / Grep / Glob` only — **no MCP, no Bash, no WebFetch**. By the time a property reaches Phase 03 the relevant files have already been resolved (in 02c) and the agent's only job is to reason about them. Letting it run shell commands or fetch external pages would be a regression — it would re-introduce the "look around hopefully" failure mode that motivated the proof-attempt approach in the first place.

**Phase 02c** is the one phase that does heavy MCP use — `tree_sitter` for symbol resolution. Phase 01a uses `fetch` for the same exploration reasons.

## MCP servers — what they do, and where

| Server | Phases | What it does |
|---|---|---|
| `fetch` | 01a | HTTP GET + HTML→Markdown for spec discovery; respects already-visited URL cache |
| `tree_sitter` | 02c | `mcp__tree_sitter__get_symbols`, `run_query`, etc. — language-aware symbol resolution without parsing files manually |

Registration: `bash scripts/setup_mcp.sh` (sets up both); `--verify` confirms each is reachable.

Why MCP for these jobs? Both are *infrastructure* the agent shouldn't reinvent. Spec crawling needs robust URL handling and HTML conversion. Symbol resolution needs a real parser per language. The MCP boundary keeps the agent prompt focused on reasoning, not on plumbing.

## Why the model split (Opus front, Sonnet back)

The first three phases (`01a` → `01b` → `01e`) build the **knowledge structure**: the spec corpus, the program graph, the typed property set. Errors at this layer cap recall — coverage of any audit run is bounded by the property quality. We use **Opus** here because RQ2 ablations showed property generation, not back-end reasoning, is the binding constraint on coverage.

The last three phases (`02c` → `03` → `04`) **verify** properties against an implementation. The 88.9% precision in RQ2 was achieved with **Sonnet 4.5** — same precision as Claude 3.7 Sonnet at lower cost than Sonnet 4. The choice is an empirical sweet spot, discussed at length in [model-benchmark takeaways](../design-notes/model-benchmark-takeaways.md).

## Reading the prompts

The prompts are short (most are 100–300 lines). If you want to understand any phase's behavior end-to-end, the prompt file is the single source of truth — the orchestrator only forwards inputs and saves outputs. A few invariants the prompts share:

- Every prompt declares its IO contract in a `<task>` block at the top (queue file, context file, output file).
- Every prompt has a `<critical_requirements>` block listing non-negotiables (e.g., "always write the output file even when the item is skipped").
- Phases 03 and 04 explicitly forbid early exits and shortcut reasoning — empirically this was the highest-leverage change to suppress hallucinated findings.

## Extending the system

To add a phase you write three artifacts:

1. A `PhaseConfig` entry in `scripts/orchestrator/config.py`.
2. A worker prompt (inline) or a skill (`.claude/skills/<name>/SKILL.md`).
3. A Pydantic schema in `scripts/orchestrator/schemas.py` for the new output type.

The orchestrator picks up the new config automatically. The CLI's phase whitelist (`KNOWN_PHASE_IDS`) emits a warning for unknown IDs but forwards them, so downstream forks can experiment without modifying `cli/`.
