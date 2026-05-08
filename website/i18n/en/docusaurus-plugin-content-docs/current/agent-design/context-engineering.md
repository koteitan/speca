---
sidebar_position: 4
---

# Context engineering

The most consequential SPECA design decisions aren't visible from reading the prompts or the orchestrator code in isolation — they live in **what each phase puts into the context window of the next phase**, and what is deliberately kept out. This page collects those decisions in one place.

## 1. The subgraph index — making spec context scale

**Problem.** Phase 02c needs to map every property back to its spec context (which function names appear, which states are involved) so it can ground tree-sitter symbol resolution. If 02c re-reads every Phase 01b partial for every property, context use balloons to the point that each item costs more in tokens than the resolution itself.

**Solution.** At Phase 02c load time, the orchestrator builds `outputs/01b_SUBGRAPH_INDEX.json` once — a compact reverse index from spec element IDs to the relevant fields (function names, state transitions, mermaid file paths). The worker prompt receives the index as part of its context and looks up only the entries it needs.

**Result.** Phase 02c's per-item context shrinks from "all 01b partials" to "one subgraph index hit + the property body." We measured this as the dominant contributor to the 40–60% Phase 03 token reduction reported in CLAUDE.md.

The index is rebuilt on every Phase 02c run. It is not committed and is not part of the inter-phase contract; it is a derived artifact owned by the orchestrator.

## 2. Code pre-resolution in 02c — pay once, save in 03

**Problem.** If Phase 03 (the audit) had to discover the right code locations for each property by itself, every audit would start with a search/read flailing phase. Empirically that flailing was the largest single cost line on early SPECA runs.

**Solution.** A whole phase (02c) sits between property generation and audit, doing nothing but pre-resolution:

- For each property, find the primary code symbol (function, struct, modifier).
- Record file path + line range + role (`primary` / `caller` / `callee` / `state-management`).
- Mark properties whose symbols don't resolve as `not_found` / `specification_only` / `out_of_scope` so 03 can skip them cheaply.
- Drop `Informational` properties at this stage — they don't justify an audit budget.

**Result.** Phase 03 receives properties with a `code_scope` field already populated. Its prompt can require the agent to use the pre-resolution and short-circuit otherwise: a real-world Phase 03 invocation is now mostly proof reasoning, not code grepping.

This is the kind of decision that doesn't read as "interesting" in a prompt diff but pays for itself a thousand times over the lifetime of a benchmark run.

## 3. Recall-safe gate ordering in Phase 04

**Problem.** A 3-gate filter is only as good as its ordering and its rejection criteria. The naive design — *"check scope first, since most things are in-scope"* — would be fast but would let dead-code findings consume gate-3 budget for no reason.

**Solution.** Gates are ordered by *cheapest correct rejection*, with early exit on `DISPUTED_FP`:

1. **Dead Code** — purely structural. The cheapest gate, with the strictest "no false reject" criterion (only fires on `unreachable!` / `panic!` / unreachable return / explicit stub).
2. **Trust Boundary** — semantic. Asks whether the input crossing the proof gap is attacker-controllable. Larger surface, but a rejection here is well-grounded (a specific input is identified as internal).
3. **Scope Check** — policy. Asks whether the proof gap's location is in `BUG_BOUNTY_SCOPE.json`'s `in_scope`. Cheapest semantically (a path match) but placed last because it would otherwise eat findings the first two gates would have explained more usefully.

The [Phase 03 vs 04 chart](../results-overview.md#how-much-does-the-3-gate-filter-help) shows recall held at 100% across the filter while precision rose from 56.9% → 66.7%. That recall is the empirical evidence that the gate ordering and rejection criteria are calibrated correctly.

**Why no gate may "soft-reject."** A gate either declares `DISPUTED_FP` (and the finding is filtered) or passes the finding through unchanged. There is no "downgrade" verdict at gate level. Downgrades happen separately, after all gates pass. This matters because it makes recall analysis tractable: if a true positive was dropped, we know exactly which gate dropped it.

## 4. Partial files as the inter-phase contract

The `outputs/<phase>_PARTIAL_*.json` files aren't a logging artifact — they are *the* inter-phase contract. Every downstream phase consumes upstream partials via glob.

This has three useful properties:

1. **Resume is a directory scan.** No state DB, no run UUIDs, no reconciliation. Crash recovery is "list the partials, skip those item IDs."
2. **Partial outputs are first-class.** A phase that completes 80% of its items writes 80% of the partials and the next phase consumes those 80% directly. This is what makes `--budget`-bounded runs useful: you can iterate on the cheap-but-incomplete output.
3. **Cross-phase validation happens at glob time.** When 02c reads 01e partials, it validates each file against the Phase 01e Pydantic schema. A schema drift between phases fails loudly at the boundary, not silently in the middle of an audit.

The trade-off: lots of files. We accept the disk usage because the alternative (a SQLite or worse) is opaque, harder to grep, and harder to publish as benchmark artifacts.

## 5. The slim 01e schema — `covers` is a string

Earlier iterations of Phase 01e attached rich subgraph context to every property: list of states, list of transitions, full RFC 2119 quotation. We discovered that **none of this context was used by Phase 02c** (which has the subgraph index) or **Phase 03** (which has the code pre-resolution). The rich context was dead weight that only served to make 01e partials bigger.

Today's `01e_PARTIAL_*.json` is intentionally lean:

- `covers` is a single string (the primary spec element ID, e.g. `"FN-001"`) — not a list of subgraph fragments.
- `reachability` has exactly four fields: `classification`, `entry_points`, `attacker_controlled`, `bug_bounty_scope`.

The principle: **what isn't consumed downstream shouldn't be produced upstream.** It's tempting to "leave room for future use cases" by emitting verbose schemas; in practice that just slows every subsequent phase.

## 6. Domain-agnostic STRIDE + CWE Top 25 — no Ethereum hardcoding

Phase 01e is the brain of the property generator. An early version had Ethereum-specific templates ("for consensus protocols, ask about fork choice"). This was fast for Ethereum work but locked the system out of any other domain.

The current Phase 01e prompt uses **STRIDE as a general thinking framework** and **CWE Top 25 (CWE-22 / 78 / 89 / 94 / 200 / 502 / 639 / 770 / 862) as concrete patterns**. The Ethereum-specific knowledge enters via `BUG_BOUNTY_SCOPE.json`, not the prompt.

This is what makes the same SPECA build work on RQ1 (Ethereum clients), RQ2 (random C/C++ OSS), and the exploratory protocol-fuzzing track in [RQ2b](../operations/benchmark-rq2b.md) without prompt forks.

## 7. Why the orchestrator never edits prompts

Some agent frameworks dynamically construct or mutate prompts based on phase state. SPECA does not. Each prompt is a static file under `prompts/`. The orchestrator's only job is to substitute three template fields (`QUEUE_FILE`, `CONTEXT_FILE`, `OUTPUT_FILE`) and forward the file to `claude --prompt-path`.

The reason: **dynamic prompts are unreviewable.** If the audit pipeline mutates its own instructions at runtime, you can no longer point at a single artifact and say "this is what the agent was told to do for that finding." Static prompts under git are how SPECA keeps the proof-attempt method auditable end-to-end.

## In summary

The decisions on this page are what separate SPECA's output from a generic "let an agent loose on a repo" pipeline:

- **Subgraph index** — decouple context volume from per-item cost.
- **Code pre-resolution** — pay 02c once, skip the flailing in 03.
- **Recall-safe gate ordering** — cheap rejections first, semantic next, policy last; no soft-rejects.
- **Partial files as contract** — resume is free, validation is at the boundary.
- **Slim 01e** — what isn't consumed isn't produced.
- **Domain-agnostic Phase 01e** — domain knowledge enters via `BUG_BOUNTY_SCOPE.json`, never the prompt.
- **Static prompts** — every audit decision traces to a single committed artifact.
